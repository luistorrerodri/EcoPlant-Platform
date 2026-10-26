import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.device import Device
from app.models.health_summary import HealthSummary
from app.models.plant_photo_diagnosis import PlantPhotoDiagnosis
from app.services import health_analysis, mqtt_client
from app.services.notify import notify_owner
from app.services.weekly_message import build_weekly_notification

logger = logging.getLogger("ecoplant.health_scheduler")

# Cada cuanto se considera que un dispositivo "toca" resumen nuevo. Se
# compara contra la fecha guardada en BD (no un temporizador en memoria),
# para que sobreviva a un reinicio del servicio sin duplicar ni saltarse
# resumenes. El calculo NO avisa por push: el aviso es semanal, aparte
# (ver _send_weekly_notifications) - los resumenes siguen calculandose
# cada 4 dias porque el ajuste automatico de riego necesita dos seguidos.
DUE_INTERVAL_DAYS = health_analysis.WINDOW_DAYS

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
            except Exception:
                logger.exception("Fallo calculando el resumen de salud de %s", device.device_id)
                db.rollback()
    finally:
        db.close()


def _send_weekly_notifications() -> None:
    # Un aviso por macetero, con lo que haya del ultimo resumen guardado
    # (puede tener hasta ~4 dias, es lo que se pidio: "lo que haya del
    # ultimo resumen") mas el recordatorio de la foto si hace falta - ver
    # app/services/weekly_message.py. Sustituye al aviso que antes salia
    # con cada resumen de salud y al recordatorio de foto aparte a los 10
    # dias: ahora es uno solo, semanal.
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        devices = db.query(Device).filter(Device.claimed_at.isnot(None)).all()
        for device in devices:
            # Mismo aislamiento por dispositivo que en _run_due_devices.
            try:
                last = (
                    db.query(HealthSummary)
                    .filter(HealthSummary.device_id == device.device_id)
                    .order_by(HealthSummary.created_at.desc())
                    .first()
                )
                photo = db.get(PlantPhotoDiagnosis, device.device_id)
                notification = build_weekly_notification(
                    last.verdict if last else None,
                    last.message if last else None,
                    photo.created_at if photo else None,
                    now,
                )
                if notification is not None:
                    notify_owner(device.device_id, *notification)
            except Exception:
                logger.exception("Fallo enviando el aviso semanal de %s", device.device_id)
                db.rollback()
    finally:
        db.close()


def start() -> None:
    # Resumenes: cada dia a las 06:00 UTC se comprueba cuales "tocan"
    # (cada 4 dias, ver DUE_INTERVAL_DAYS). Antes a las 09:00 UTC, pero
    # en verano eso es exactamente las 11:00 de Madrid y coincidia al
    # minuto con el aviso semanal - asi el aviso siempre usa un resumen
    # ya calculado.
    _scheduler.add_job(_run_due_devices, "cron", hour=6, id="health_summary_daily")
    # Aviso semanal: domingo a las 11:00 hora de Madrid (confirmado con
    # Luis, 2026-10-26), con su propio huso para que siga siendo las 11
    # tras los cambios de hora. coalesce/grace: si el hilo del scheduler
    # llega tarde (hasta 1h) se envia igualmente, una sola vez.
    _scheduler.add_job(
        _send_weekly_notifications,
        CronTrigger(day_of_week="sun", hour=11, minute=0, timezone="Europe/Madrid"),
        id="health_weekly_notification",
        coalesce=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    weekly = _scheduler.get_job("health_weekly_notification")
    logger.info("Aviso semanal programado; proxima ejecucion: %s", weekly.next_run_time if weekly else "?")


def stop() -> None:
    _scheduler.shutdown(wait=False)
