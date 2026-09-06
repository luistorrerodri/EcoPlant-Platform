import json
import logging
import ssl
import threading

import paho.mqtt.client as mqtt

from app.config import settings

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


def _send_notification(device_id: str, title: str, body: str) -> None:
    # Import diferido para evitar un ciclo de imports (database/models
    # no necesitan saber nada de mqtt_client).
    from app.database import SessionLocal
    from app.models.device import Device
    from app.services.push import send_push_notification

    db = SessionLocal()
    try:
        device = db.get(Device, device_id)
        if device is None or device.location is None:
            return
        owner = device.location.owner
        if owner.push_token:
            send_push_notification(owner.push_token, title, body)
    finally:
        db.close()


def _notify_if_still_offline(device_id: str) -> None:
    # Se ejecuta DISCONNECT_GRACE_SECONDS despues del aviso de
    # desconexion, en un hilo aparte (threading.Timer). Si en ese margen
    # ha llegado un online:true, _last_online_state ya no dira False y
    # el aviso se descarta - era un parpadeo, no una desconexion real.
    if _last_online_state.get(device_id) is not False:
        return
    _send_notification(
        device_id, "Dispositivo desconectado", f"{device_id} se ha desconectado inesperadamente."
    )


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
        _send_notification(device_id, "Riego completado", f"{device_id} ha terminado de regar.")


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
    result = _client.publish(f"maceteros/{device_id}/comando", "REGAR", qos=1)
    result.wait_for_publish(timeout=5)
