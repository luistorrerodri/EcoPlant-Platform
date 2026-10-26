from datetime import datetime, timedelta

# Si la ultima foto analizada tiene mas de esto (o no hay ninguna), el
# aviso semanal incluye el recordatorio de hacer una nueva - sin foto
# reciente, el resumen por sensores no cuenta la parte visual del
# diagnostico (ver plant_vision.py).
PHOTO_STALE_DAYS = 7


def build_weekly_notification(
    summary_verdict: str | None,
    summary_message: str | None,
    photo_created_at: datetime | None,
    now: datetime,
) -> tuple[str, str] | None:
    # (titulo, cuerpo) del aviso semanal de un macetero, o None si no hay
    # nada util que decir todavia (sin ningun resumen, o con datos
    # insuficientes - un dispositivo nuevo o sin datos no necesita un
    # aviso semanal; si esta desconectado ya avisa el push de desconexion).
    # "{device_name}" lo sustituye notify_owner con el nombre amigable.
    if summary_verdict is None or summary_message is None or summary_verdict == "datos_insuficientes":
        return None

    body = summary_message
    if photo_created_at is None:
        body += " 📷 Todavía no hay ninguna foto: haz una para un diagnóstico completo."
    elif now - photo_created_at > timedelta(days=PHOTO_STALE_DAYS):
        body += " 📷 La última foto tiene más de una semana: haz una nueva para un diagnóstico completo."
    return "Revisión semanal de {device_name}", body
