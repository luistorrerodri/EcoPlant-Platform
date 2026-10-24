import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.device import Device
from app.models.health_summary import HealthSummary
from app.models.plant_photo_diagnosis import PlantPhotoDiagnosis
from app.services import health_analysis, mqtt_client
from app.services.notify import notify_owner

logger = logging.getLogger("ecoplant.health_scheduler")

# Cada cuanto se considera que un dispositivo "toca" resumen nuevo. Se
# compara contra la fecha guardada en BD (no un temporizador en memoria),
# para que sobreviva a un reinicio del servicio sin duplicar ni saltarse
# resumenes.
DUE_INTERVAL_DAYS = health_analysis.WINDOW_DAYS

# Si la ultima foto analizada es mas antigua que esto (o no existe
# ninguna), el aviso periodico deja de mandar el mensaje de solo-sensores
# (que "dice cosas a medias" sin la foto, ver plant_vision.py) y en su
# lugar recuerda subir una nueva - mayor que DUE_INTERVAL_DAYS porque
# hacer una foto es mas esfuerzo que una lectura pasiva de sensores, no
# tiene sentido pedirla con la misma frecuencia.
PHOTO_STALE_DAYS = 10

# Ajuste automatico de la duracion de riego: confirmado con Luis
# (2026-10-24). Se basa solo en pct_tiempo_bajo_minimo via el veredicto
# revisar_riego - una lectura real del sensor, nunca en que disparo un
# riego concreto, para que un riego manual de prueba no cuente para nada
# (ni para bien ni para mal). Dispara una vez cuando se forma una racha
# NUEVA de 2 resumenes seguidos en revisar_riego (no en cada resumen
# mientras el problema continua sin resolverse) - ver _maybe_auto_tune_duration.
AUTO_TUNE_INCREMENT_MS = 1000
AUTO_TUNE_MAX_EXTRA_MS = 4000

_scheduler = BackgroundScheduler(timezone="UTC")


def _maybe_auto_tune_duration(
    device: Device, db: Session, current_verdict: str, previous: HealthSummary | None, before_previous: HealthSummary | None
) -> None:
    racha_nueva_de_dos = (
        current_verdict == "revisar_riego"
        and previous is not None
        and previous.verdict == "revisar_riego"
        and (before_previous is None or before_previous.verdict != "revisar_riego")
    )
    if not racha_nueva_de_dos:
        return
    tope = device.duracion_riego_base_ms + AUTO_TUNE_MAX_EXTRA_MS
    if device.duracion_riego_ms >= tope:
        return
    nueva_duracion = min(device.duracion_riego_ms + AUTO_TUNE_INCREMENT_MS, tope)
    device.duracion_riego_ms = nueva_duracion
    db.commit()
    mqtt_client.publish_device_config(
        device.device_id,
        device.humedad_min,
        device.humedad_max,
        device.soil_dry_raw,
        device.soil_wet_raw,
        device.duracion_riego_ms,
    )
    notify_owner(
        device.device_id,
        "Riego ajustado automáticamente",
        "{device_name} ha necesitado riego varios días seguidos, así que se ha alargado cada riego a "
        f"{nueva_duracion // 1000}s para que le llegue más agua. Puedes cambiarlo desde Configuración si no "
        "te parece bien.",
    )


def _run_due_devices() -> None:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=DUE_INTERVAL_DAYS)
        devices = db.query(Device).filter(Device.claimed_at.isnot(None)).all()
        for device in devices:
            # Todo el cuerpo del dispositivo en un unico try/except: un fallo
            # con uno (tabla no lista, Influx caido, lo que sea) no debe
            # cortar la evaluacion del resto - se vio en real la primera vez
            # que se desplego esto. El rollback es necesario porque Postgres
            # deja la sesion "abortada" tras un error, y sin el, cualquier
            # consulta del siguiente dispositivo en esta misma sesion
            # fallaria tambien aunque no tenga nada que ver.
            try:
                # Los 2 mas recientes de una vez: el primero es el mismo
                # "last" de siempre (para el corte de DUE_INTERVAL_DAYS),
                # el segundo hace falta para el ajuste automatico de riego
                # mas abajo (saber si la racha de revisar_riego es nueva).
                recientes = (
                    db.query(HealthSummary)
                    .filter(HealthSummary.device_id == device.device_id)
                    .order_by(HealthSummary.created_at.desc())
                    .limit(2)
                    .all()
                )
                last = recientes[0] if recientes else None
                anterior_a_last = recientes[1] if len(recientes) > 1 else None
                if last is not None and last.created_at > cutoff:
                    continue
                result = health_analysis.compute_health_summary(device, db)
                summary = HealthSummary(device_id=device.device_id, **result.__dict__)
                db.add(summary)
                db.commit()
                _maybe_auto_tune_duration(device, db, result.verdict, last, anterior_a_last)
                if result.verdict != "datos_insuficientes":
                    photo = db.get(PlantPhotoDiagnosis, device.device_id)
                    photo_stale = photo is None or photo.created_at < datetime.now(timezone.utc) - timedelta(
                        days=PHOTO_STALE_DAYS
                    )
                    if photo_stale:
                        # Sin foto reciente, el mensaje de solo-sensores de
                        # arriba (result.message) no cuenta la parte visual
                        # del diagnostico - mejor pedir la foto que mandar
                        # un aviso a medias. result.message no se toca (se
                        # guarda igual en la BD, lo sigue usando la app),
                        # esto solo cambia el texto del push.
                        notify_owner(
                            device.device_id,
                            "Actualiza el diagnóstico de tu planta",
                            "Hace tiempo que no subes una foto de {device_name} - el diagnóstico de ahora mismo "
                            "solo tiene en cuenta los sensores. Sube una nueva para ver el estado completo.",
                        )
                    else:
                        notify_owner(device.device_id, "Resumen de salud de tu planta", result.message)
            except Exception:
                logger.exception("Fallo calculando el resumen de salud de %s", device.device_id)
                db.rollback()
    finally:
        db.close()


def start() -> None:
    _scheduler.add_job(_run_due_devices, "cron", hour=9, id="health_summary_daily")
    _scheduler.start()


def stop() -> None:
    _scheduler.shutdown(wait=False)
