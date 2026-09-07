import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.models.device import Device
from app.models.health_summary import HealthSummary
from app.services import health_analysis
from app.services.notify import notify_owner

logger = logging.getLogger("ecoplant.health_scheduler")

# Cada cuanto se considera que un dispositivo "toca" resumen nuevo. Se
# compara contra la fecha guardada en BD (no un temporizador en memoria),
# para que sobreviva a un reinicio del servicio sin duplicar ni saltarse
# resumenes.
DUE_INTERVAL_DAYS = health_analysis.WINDOW_DAYS

_scheduler = BackgroundScheduler(timezone="UTC")


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
                last = (
                    db.query(HealthSummary)
                    .filter(HealthSummary.device_id == device.device_id)
                    .order_by(HealthSummary.created_at.desc())
                    .first()
                )
                if last is not None and last.created_at > cutoff:
                    continue
                result = health_analysis.compute_health_summary(device, db)
                summary = HealthSummary(device_id=device.device_id, **result.__dict__)
                db.add(summary)
                db.commit()
                if result.verdict != "datos_insuficientes":
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
