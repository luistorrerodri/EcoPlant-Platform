import json
import logging
import ssl
import threading

import paho.mqtt.client as mqtt

from app.config import settings
from app.services.notify import notify_owner
from app.services.time_utils import device_unix_to_utc
from app.services.watering_origin import consume_origin, mark_manual

logger = logging.getLogger("ecoplant.mqtt")

# Antes de avisar de una desconexion se espera este margen por si el
# dispositivo se reconecta solo: con el keepalive corto que usa hoy el
# firmware (15s, valor por defecto de PubSubClient), un corte de wifi de
# apenas un par de segundos ya hace que el broker dispare el LWT
# (online:false) - sin este margen, cualquier parpadeo transitorio de
# la red generaba una notificacion push aunque el dispositivo se
# recuperase solo unos segundos despues.
DISCONNECT_GRACE_SECONDS = 30

# Ultimo estado online/offline visto por dispositivo, para poder
# comprobar en el momento del aviso si sigue realmente desconectado.
_last_online_state: dict[str, bool] = {}

_client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="backend-api",
)
_client.tls_set(
    ca_certs=settings.mqtt_ca_cert_path,
    certfile=settings.mqtt_client_cert_path,
    keyfile=settings.mqtt_client_key_path,
    tls_version=ssl.PROTOCOL_TLSv1_2,
)


def _on_connect(client, userdata, flags, reason_code, properties) -> None:
    logger.info("MQTT conectado (reason_code=%s)", reason_code)
    client.subscribe("maceteros/+/estado")


def _on_disconnect(client, userdata, flags, reason_code, properties) -> None:
    logger.warning("MQTT desconectado (reason_code=%s)", reason_code)


def _notify_if_still_offline(device_id: str) -> None:
    # Se ejecuta DISCONNECT_GRACE_SECONDS despues del aviso de
    # desconexion, en un hilo aparte (threading.Timer). Si en ese margen
    # ha llegado un online:true, _last_online_state ya no dira False y
    # el aviso se descarta - era un parpadeo, no una desconexion real.
    if _last_online_state.get(device_id) is not False:
        return
    notify_owner(
        device_id, "Dispositivo desconectado", "{device_name} se ha desconectado inesperadamente."
    )


def _persist_watering_event(device_id: str, payload: dict) -> None:
    # Import diferido, mismo motivo que en app.services.notify.
    from app.database import SessionLocal
    from app.models.watering_event import WateringEvent

    try:
        timestamp = device_unix_to_utc(payload["timestamp"])
        duration_ms = payload["duracion_ms"]
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        logger.warning("Evento riego_completado de %s sin timestamp/duracion_ms valido: %s", device_id, payload)
        return

    db = SessionLocal()
    try:
        db.add(WateringEvent(
            device_id=device_id,
            timestamp=timestamp,
            duration_ms=duration_ms,
            origen=consume_origin(device_id),
        ))
        db.commit()
    except Exception:
        logger.exception("No se pudo guardar el evento de riego de %s", device_id)
        db.rollback()
    finally:
        db.close()


def _on_message(client, userdata, message) -> None:
    try:
        device_id = message.topic.split("/")[1]
        payload = json.loads(message.payload.decode())
    except (IndexError, ValueError):
        return

    if payload.get("online") is False:
        _last_online_state[device_id] = False
        threading.Timer(DISCONNECT_GRACE_SECONDS, _notify_if_still_offline, args=(device_id,)).start()
    elif payload.get("online") is True:
        _last_online_state[device_id] = True
    elif payload.get("evento") == "riego_completado":
        _persist_watering_event(device_id, payload)
        notify_owner(device_id, "Riego completado", "{device_name} ha terminado de regar.")


_client.on_connect = _on_connect
_client.on_disconnect = _on_disconnect
_client.on_message = _on_message


def start() -> None:
    # connect_async + loop_start: si Mosquitto no esta listo todavia,
    # el arranque del API no debe bloquearse ni caerse por ello -
    # paho reintenta la conexion en segundo plano por su cuenta.
    _client.connect_async(settings.mqtt_host, settings.mqtt_port)
    _client.loop_start()


def stop() -> None:
    _client.loop_stop()
    _client.disconnect()


def publish_water_command(device_id: str) -> None:
    # Solo el riego MANUAL pasa por aqui (el automatico lo publica
    # Node-RED directamente): apuntarlo despues de publicar es lo que
    # permite etiquetar luego el riego como manual - ver
    # app/services/watering_origin.py.
    result = _client.publish(f"maceteros/{device_id}/comando", "REGAR", qos=1)
    result.wait_for_publish(timeout=5)
    mark_manual(device_id)


def publish_device_config(
    device_id: str,
    humedad_min: int,
    humedad_max: int,
    soil_dry_raw: int,
    soil_wet_raw: int,
    duracion_riego_ms: int,
) -> None:
    # Retained: un dispositivo que se reinicia recibe la ultima config
    # conocida al reconectar, sin esperar a que alguien vuelva a tocar
    # la configuracion desde la app. El servidor sigue siendo quien
    # decide los umbrales (y la calibracion del sensor) - el dispositivo
    # solo los aplica para su propia pantalla, igual que ya recibe el
    # comando "REGAR" sin decidir cuando regar.
    payload = json.dumps({
        "humedadMin": humedad_min,
        "humedadMax": humedad_max,
        "soilDry": soil_dry_raw,
        "soilWet": soil_wet_raw,
        "duracionRiegoMs": duracion_riego_ms,
    })
    result = _client.publish(f"maceteros/{device_id}/config", payload, qos=1, retain=True)
    result.wait_for_publish(timeout=5)
