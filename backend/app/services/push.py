import logging

import requests

logger = logging.getLogger("ecoplant.push")

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_push_notification(push_token: str, title: str, body: str) -> bool:
    # API publica de Expo: no hace falta credencial propia, solo el
    # token de push del dispositivo destino. Devuelve False solo cuando
    # Expo dice que ese token ya no existe (app desinstalada, datos
    # borrados...) para que quien llama lo borre - cualquier otro fallo
    # (red, error transitorio) devuelve True: el token puede seguir
    # siendo valido.
    try:
        response = requests.post(
            EXPO_PUSH_URL,
            json={"to": push_token, "title": title, "body": body},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        if not response.ok:
            logger.warning("Push a Expo fallo (%s): %s", response.status_code, response.text)
            return True
        try:
            ticket = response.json().get("data")
        except ValueError:
            return True
        if isinstance(ticket, dict) and ticket.get("status") == "error":
            error = (ticket.get("details") or {}).get("error")
            logger.warning("Expo rechazo el push (%s): %s", error, ticket.get("message"))
            if error == "DeviceNotRegistered":
                return False
    except requests.RequestException:
        logger.exception("Error de red enviando push a Expo")
    return True
