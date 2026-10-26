from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Zona horaria que usa el firmware (configTzTime("CET-1CEST,...")) para
# dejar el RTC en hora local - ver sincronizarHora() en el .ino.
DEVICE_TIMEZONE = ZoneInfo("Europe/Madrid")


def device_unix_to_utc(timestamp: int | float) -> datetime:
    # El RTC del ESP32 guarda la hora LOCAL (se ajusta con la hora NTP ya
    # convertida a CET/CEST), pero rtc.now().unixtime() la presenta como
    # si fuera UTC: el "timestamp" que viaja en el ack del riego es la
    # hora de pared de Madrid etiquetada como epoch. Guardarlo tal cual
    # dejaba watering_events 1h (invierno) / 2h (verano) por delante de
    # la realidad, y desalineado con los puntos de InfluxDB (esos si son
    # UTC reales) - ver docs/troubleshooting.md #39.
    wall_clock = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
    return wall_clock.replace(tzinfo=DEVICE_TIMEZONE).astimezone(timezone.utc)
