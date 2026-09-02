import logging
import ssl

import paho.mqtt.client as mqtt

from app.config import settings

logger = logging.getLogger("ecoplant.mqtt")

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


def _on_disconnect(client, userdata, flags, reason_code, properties) -> None:
    logger.warning("MQTT desconectado (reason_code=%s)", reason_code)


_client.on_connect = _on_connect
_client.on_disconnect = _on_disconnect


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
