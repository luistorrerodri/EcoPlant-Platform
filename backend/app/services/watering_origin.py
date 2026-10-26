import threading
import time

ORIGIN_MANUAL = "manual"
ORIGIN_AUTOMATIC = "automatico"

# Margen entre "el usuario pulso Regar ahora" y "llega la confirmacion del
# riego": el firmware riega hasta TIEMPO_RIEGO_MAX (30s) mas la latencia
# MQTT, asi que 90s cubre cualquier riego manual normal sin arrastrar un
# marcador viejo hasta el siguiente riego automatico.
MANUAL_WINDOW_SECONDS = 90

# El riego automatico lo ordena Node-RED directamente por MQTT, sin pasar
# por el backend - la unica forma de saber que un riego fue manual es que
# el propio backend lo apunte al publicar la orden. Solo en memoria: un
# reinicio del backend a mitad de un riego manual lo etiquetaria como
# automatico, un caso muy raro y de poca consecuencia.
_lock = threading.Lock()
_pending_manual: dict[str, float] = {}


def mark_manual(device_id: str, now: float | None = None) -> None:
    with _lock:
        _pending_manual[device_id] = time.time() if now is None else now


def consume_origin(device_id: str, now: float | None = None) -> str:
    # Devuelve "manual" si hay una orden manual reciente para este
    # dispositivo (y la gasta, para que un solo clic etiquete un solo
    # riego), o "automatico" en cualquier otro caso.
    current = time.time() if now is None else now
    with _lock:
        marked_at = _pending_manual.pop(device_id, None)
    if marked_at is not None and current - marked_at <= MANUAL_WINDOW_SECONDS:
        return ORIGIN_MANUAL
    return ORIGIN_AUTOMATIC
