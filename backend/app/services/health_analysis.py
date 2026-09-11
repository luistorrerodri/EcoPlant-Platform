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
DRY_TOO_OFTEN_THRESHOLD = 0.25  # fraccion del tiempo bajo humedad_min
SLOW_DRAINAGE_HOURS = 20.0  # horas hasta recuperar humedad_min+10 tras regar
TOO_WET_THRESHOLD = 0.5  # fraccion del tiempo por encima de humedad_max
MIN_POINTS_FOR_VERDICT = 12  # ~medio dia de lecturas agregadas a 1h
DRYING_RATE_FAST_MARGIN = 1.3  # 30% mas rapido que el ritmo esperado del tipo
DRYING_RATE_SLOW_MARGIN = 0.5  # menos de la mitad del ritmo esperado del tipo
MIN_DRYING_SEGMENT_HOURS = 3.0  # tramos de bajada mas cortos se descartan como ruido


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
    tasa_secado_pct_h: float | None


def _drying_rate_pct_h(humedad_points: list[dict]) -> float | None:
    # Tasa de secado por tramo real de bajada (de un maximo local al
    # siguiente minimo local, antes de que vuelva a subir) - no paso a
    # paso. Contar cada bajada puntual entre dos lecturas consecutivas
    # sesga el resultado al alza: en una señal plana con ruido del
    # sensor (42-41-42-41...) siempre hay bajadas puntuales que contar,
    # pero nunca se restan las subidas que las compensan, así que un
    # suelo que en realidad no se está secando puede dar una tasa
    # positiva igualmente. Los tramos mas cortos que
    # MIN_DRYING_SEGMENT_HOURS se descartan por el mismo motivo -
    # probablemente ruido, no drenaje real.
    ordenados = sorted(humedad_points, key=lambda p: p["time"])
    if len(ordenados) < 2:
        return None

    tasas: list[float] = []
    pico = ordenados[0]
    valle = ordenados[0]

    def cerrar_tramo(pico: dict, valle: dict) -> None:
        if valle["value"] >= pico["value"]:
            return
        horas = (valle["time"] - pico["time"]).total_seconds() / 3600
        if horas >= MIN_DRYING_SEGMENT_HOURS:
            tasas.append((pico["value"] - valle["value"]) / horas)

    for punto in ordenados[1:]:
        if punto["value"] > pico["value"]:
            cerrar_tramo(pico, valle)
            pico = punto
            valle = punto
        elif punto["value"] < valle["value"]:
            valle = punto
    cerrar_tramo(pico, valle)

    return sum(tasas) / len(tasas) if tasas else None


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
            tasa_secado_pct_h=None,
        )

    pct_bajo_minimo = sum(1 for p in humedad_points if p["value"] < device.humedad_min) / len(humedad_points)
    # Umbral por tipo de planta (device.humedad_max), no un porcentaje fijo:
    # mismo bug de fondo que el de "estado" arreglado hoy - un 85% fijo
    # nunca se disparaba para un cactus (humedad_max=32), aunque llevara
    # dias muy por encima de lo que tolera ese tipo de planta.
    pct_saturado = sum(1 for p in humedad_points if p["value"] > device.humedad_max) / len(humedad_points)

    recovery_threshold = device.humedad_min + 10
    recovery_samples = [
        h
        for h in (_recovery_hours(e.timestamp, humedad_points, recovery_threshold) for e in events)
        if h is not None
    ]
    tiempo_recuperacion_medio_h = sum(recovery_samples) / len(recovery_samples) if recovery_samples else None
    tasa_secado_pct_h = _drying_rate_pct_h(humedad_points)

    if pct_bajo_minimo > DRY_TOO_OFTEN_THRESHOLD:
        verdict = "revisar_riego"
        message = (
            f"El suelo ha estado por debajo del mínimo configurado ({device.humedad_min}%) durante "
            f"{pct_bajo_minimo:.0%} de los últimos {window_days} días. Puede que necesite regar más a "
            "menudo o revisar que el riego automático se esté ejecutando."
        )
    elif pct_saturado > TOO_WET_THRESHOLD:
        # Sin riegos en la ventana no hay como medir tiempo_recuperacion_medio_h
        # (se mide desde un evento de riego) - pero un suelo que pasa la
        # mayor parte del tiempo por encima de su propio maximo, aunque no
        # se haya regado, es la misma alarma real de fondo (exceso de agua).
        verdict = "revisar_drenaje"
        message = (
            f"El suelo ha estado por encima del máximo configurado ({device.humedad_max}%) durante "
            f"{pct_saturado:.0%} de los últimos {window_days} días. Puede indicar que el sustrato retiene "
            "demasiada agua o que se está regando más de lo que esta planta necesita."
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

    # Contexto del ritmo de secado frente al esperado para el tipo de
    # planta - informativo, no cambia el veredicto (es un valor estimado
    # a partir de guias de cuidado, no de datos reales, ver el plan de
    # esta iteracion; no deberia poder disparar una alarma por si solo).
    saturado_cronico = pct_saturado > TOO_WET_THRESHOLD
    esperado = device.plant_type.default_tasa_secado_max_pct_h if device.plant_type else None
    if tasa_secado_pct_h is not None and esperado is not None:
        if tasa_secado_pct_h > esperado * DRYING_RATE_FAST_MARGIN:
            if saturado_cronico:
                # Un secado rapido aqui es una buena noticia, no una alarma
                # aparte: explica que el exceso de agua detectado arriba
                # deberia resolverse solo, en vez de sonar contradictorio.
                message += (
                    " De todas formas, se está secando más rápido de lo habitual para este tipo de "
                    "planta, lo que hará que vuelva a niveles normales en breve."
                )
            else:
                message += " Se seca más rápido de lo habitual para este tipo de planta."
        elif tasa_secado_pct_h < esperado * DRYING_RATE_SLOW_MARGIN:
            message += " Se seca más despacio de lo habitual para este tipo de planta — vigila que no quede agua estancada."
        else:
            message += " El ritmo de secado es el esperado para este tipo de planta."

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
        tasa_secado_pct_h=tasa_secado_pct_h,
    )
