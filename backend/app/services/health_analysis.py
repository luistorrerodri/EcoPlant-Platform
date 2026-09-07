from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.watering_event import WateringEvent
from app.services import influx_client

# Umbrales de arranque, deliberadamente simples (estadistica descriptiva,
# no ML) - con solo unos dias de historico no hay datos para entrenar ni
# validar nada mas sofisticado. Pensados para ajustarse con uso real.
WINDOW_DAYS = 4
SATURATION_THRESHOLD = 85.0  # % de humedad de suelo, "posible encharcamiento"
DRY_TOO_OFTEN_THRESHOLD = 0.25  # fraccion del tiempo bajo humedad_min
SLOW_DRAINAGE_HOURS = 20.0  # horas hasta recuperar humedad_min+10 tras regar
MIN_POINTS_FOR_VERDICT = 12  # ~medio dia de lecturas agregadas a 1h


@dataclass
class HealthSummaryResult:
    window_days: int
    verdict: str
    message: str
    pct_tiempo_bajo_minimo: float | None
    pct_tiempo_saturado: float | None
    num_riegos: int
    tiempo_recuperacion_medio_h: float | None
    temp_suelo_min: float | None
    temp_suelo_max: float | None
    temp_aire_min: float | None
    temp_aire_max: float | None


def _extremes(points: list[dict]) -> tuple[float | None, float | None]:
    values = [p["value"] for p in points]
    if not values:
        return None, None
    return min(values), max(values)


def _recovery_hours(
    event_time: datetime, humedad_points: list[dict], recovery_threshold: float
) -> float | None:
    # Horas desde el riego hasta que humedad_suelo vuelve a bajar del
    # umbral de recuperacion. None si no hay suficiente lectura posterior
    # todavia (el riego es demasiado reciente) o si nunca baja.
    after = sorted((p for p in humedad_points if p["time"] > event_time), key=lambda p: p["time"])
    if not after:
        return None
    for point in after:
        if point["value"] < recovery_threshold:
            return (point["time"] - event_time).total_seconds() / 3600
    # Nunca bajo del umbral en toda la ventana disponible: si la ultima
    # lectura es reciente, puede que simplemente falte tiempo todavia -
    # no se cuenta como un dato valido, ni bueno ni malo.
    return None


def compute_health_summary(device: Device, db: Session, window_days: int = WINDOW_DAYS) -> HealthSummaryResult:
    readings = influx_client.get_readings(device.device_id, window_days * 24)
    humedad_points = [p for p in readings["points"] if p["field"] == "humedad_suelo"]
    temp_suelo_points = [p for p in readings["points"] if p["field"] == "temp_suelo"]
    temp_aire_points = [p for p in readings["points"] if p["field"] == "temp_aire"]

    window_start = datetime.now(timezone.utc) - timedelta(days=window_days)
    events = (
        db.query(WateringEvent)
        .filter(WateringEvent.device_id == device.device_id, WateringEvent.timestamp >= window_start)
        .order_by(WateringEvent.timestamp)
        .all()
    )

    temp_suelo_min, temp_suelo_max = _extremes(temp_suelo_points)
    temp_aire_min, temp_aire_max = _extremes(temp_aire_points)

    if len(humedad_points) < MIN_POINTS_FOR_VERDICT:
        return HealthSummaryResult(
            window_days=window_days,
            verdict="datos_insuficientes",
            message=(
                "Todavía no hay histórico suficiente de humedad de suelo para valorar cómo se está "
                "comportando la planta. Vuelve a intentarlo en uno o dos días."
            ),
            pct_tiempo_bajo_minimo=None,
            pct_tiempo_saturado=None,
            num_riegos=len(events),
            tiempo_recuperacion_medio_h=None,
            temp_suelo_min=temp_suelo_min,
            temp_suelo_max=temp_suelo_max,
            temp_aire_min=temp_aire_min,
            temp_aire_max=temp_aire_max,
        )

    pct_bajo_minimo = sum(1 for p in humedad_points if p["value"] < device.humedad_min) / len(humedad_points)
    pct_saturado = sum(1 for p in humedad_points if p["value"] > SATURATION_THRESHOLD) / len(humedad_points)

    recovery_threshold = device.humedad_min + 10
    recovery_samples = [
        h
        for h in (_recovery_hours(e.timestamp, humedad_points, recovery_threshold) for e in events)
        if h is not None
    ]
    tiempo_recuperacion_medio_h = sum(recovery_samples) / len(recovery_samples) if recovery_samples else None

    if pct_bajo_minimo > DRY_TOO_OFTEN_THRESHOLD:
        verdict = "revisar_riego"
        message = (
            f"El suelo ha estado por debajo del mínimo configurado ({device.humedad_min}%) durante "
            f"{pct_bajo_minimo:.0%} de los últimos {window_days} días. Puede que necesite regar más a "
            "menudo o revisar que el riego automático se esté ejecutando."
        )
    elif tiempo_recuperacion_medio_h is not None and tiempo_recuperacion_medio_h > SLOW_DRAINAGE_HOURS:
        verdict = "revisar_drenaje"
        message = (
            f"Tras regar, el suelo tarda de media {tiempo_recuperacion_medio_h:.0f} horas en volver a "
            "niveles normales de humedad. Puede indicar que el sustrato drena mal o que se está regando "
            "más de lo necesario."
        )
    else:
        verdict = "sana"
        message = (
            f"La planta parece estar bien: la humedad de suelo se ha mantenido dentro de rangos normales "
            f"durante los últimos {window_days} días"
            + (f", con {len(events)} riego(s) registrado(s)." if events else ".")
        )

    return HealthSummaryResult(
        window_days=window_days,
        verdict=verdict,
        message=message,
        pct_tiempo_bajo_minimo=pct_bajo_minimo,
        pct_tiempo_saturado=pct_saturado,
        num_riegos=len(events),
        tiempo_recuperacion_medio_h=tiempo_recuperacion_medio_h,
        temp_suelo_min=temp_suelo_min,
        temp_suelo_max=temp_suelo_max,
        temp_aire_min=temp_aire_min,
        temp_aire_max=temp_aire_max,
    )
