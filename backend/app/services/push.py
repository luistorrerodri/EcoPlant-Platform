import logging

import requests

logger = logging.getLogger("ecoplant.push")

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_push_notification(push_token: str, title: str, body: str) -> None:
    # API publica de Expo: no hace falta credencial propia, solo el
    # token de push del dispositivo destino.
    try:
        response = requests.post(
            EXPO_PUSH_URL,
            json={"to": push_token, "title": title, "body": body},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        if not response.ok:
            logger.warning("Push a Expo fallo (%s): %s", response.status_code, response.text)
    except requests.RequestException:
        logger.exception("Error de red enviando push a Expo")
