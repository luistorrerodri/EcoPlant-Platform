import base64
import time
from datetime import datetime, timedelta, timezone

import groq
from sqlalchemy.orm import Session

from app.config import settings
from app.models.device import Device
from app.models.watering_event import WateringEvent
from app.services import influx_client

WINDOW_HOURS = 120  # 5 dias, mismo contexto que pidio Luis
MODEL = "qwen/qwen3.8-27b"  # unico modelo con vision de Groq ahora mismo

# Tercer proveedor probado: Claude (de pago, funcionaba pero costaba)
# y despues Gemini (nivel "gratuito" que en la practica estaba topado
# de verdad para la cuenta de Luis - "Upgrade to unlock more" en AI
# Studio, no un pico de demanda como parecia al principio). Groq tiene
# un plan gratuito real y publicado (limites por dia/minuto, no un
# trial que caduca), sin tarjeta, y es una cuenta distinta de Google -
# no arrastra el uso previo que topo al otro proveedor.
MAX_INTENTOS = 3
ESPERA_ENTRE_INTENTOS_S = 5

_client = groq.Groq(api_key=settings.groq_api_key)

VERDICTS = {"bien", "revisar", "preocupante"}


def _resumen_sensores(device: Device, db: Session) -> str:
    # Mismo motivo que aggregateWindow() en get_readings: mandarle al
    # modelo cientos de puntos en crudo no aporta nada que un resumen no
    # de ya, y consume mas tokens (ver troubleshooting #17 sobre payloads
    # sin agregar). Se resume aqui, no se manda la serie completa.
    readings = influx_client.get_readings(device.device_id, WINDOW_HOURS)
    points = readings["points"]

    def _rango(field: str) -> str:
        valores = [p["value"] for p in points if p["field"] == field]
        if not valores:
            return "sin datos"
        return f"minimo {min(valores):.0f}, maximo {max(valores):.0f}, media {sum(valores) / len(valores):.0f}"

    ultima_humedad = next(
        (p["value"] for p in sorted(points, key=lambda p: p["time"], reverse=True) if p["field"] == "humedad_suelo"),
        None,
    )

    plant_type_name = device.plant_type.name if device.plant_type else "sin especificar"
    humedad_ahora = f"{ultima_humedad:.0f}%" if ultima_humedad is not None else "sin datos"

    return (
        f"Tipo de planta: {plant_type_name}\n"
        f"Humedad de suelo objetivo configurada: {device.humedad_min}-{device.humedad_max}%\n"
        f"Humedad de suelo ahora mismo: {humedad_ahora}\n"
        f"Humedad de suelo, ultimos 5 dias: {_rango('humedad_suelo')}\n"
        f"Temperatura de sustrato, ultimos 5 dias: {_rango('temp_suelo')}\n"
        f"Temperatura de aire, ultimos 5 dias: {_rango('temp_aire')}\n"
        f"Riegos en los ultimos 5 dias: {_num_riegos(device, db)}"
    )


def _num_riegos(device: Device, db: Session) -> int:
    # Mismo patron de consulta que health_analysis.py, misma tabla y
    # misma sesion que ya trae el router - no abrir una segunda sesion
    # aparte solo para este conteo. Ventana fija de 5 dias (WINDOW_HOURS),
    # distinta de la ventana configurable de health_analysis.py.
    window_start = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    return (
        db.query(WateringEvent)
        .filter(WateringEvent.device_id == device.device_id, WateringEvent.timestamp >= window_start)
        .count()
    )


def _parse_respuesta(texto: str) -> tuple[str, str]:
    primera_linea, _, resto = texto.strip().partition("\n")
    verdict = primera_linea.strip().lower().strip(".:,;")
    if verdict not in VERDICTS:
        raise ValueError(f"Respuesta del modelo sin veredicto reconocible: {texto[:200]!r}")
    return verdict, resto.strip()


def _image_part(data: bytes, mime_type: str) -> dict:
    # Groq usa el mismo formato "image_url" con data URI que la API de
    # OpenAI (su SDK sigue esa convencion) - no hay un tipo "image" con
    # bytes en crudo como tenia el SDK de Gemini.
    encoded = base64.b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}}


def diagnose_plant(
    photo_bytes: bytes,
    content_type: str,
    device: Device,
    db: Session,
    previous_photo: tuple[bytes, str] | None = None,
) -> tuple[str, str]:
    """Devuelve (verdict, message). Lanza excepcion si la llamada a la API falla
    o la respuesta no se puede interpretar - el router decide que hacer con eso,
    aqui no se guarda nada a medias."""

    contexto = _resumen_sensores(device, db)

    instrucciones = (
        "Eres un asistente que valora la salud de una planta de interior/exterior a partir de "
        "una foto y datos de sus sensores de suelo y ambiente. Responde SIEMPRE en este formato "
        "exacto, en español:\n"
        "- Primera línea: una única palabra, exactamente una de estas tres: bien, revisar, preocupante.\n"
        "- Resto: 2-4 frases explicando el porqué, en tono cercano, sin tecnicismos innecesarios.\n"
    )
    if previous_photo is not None:
        instrucciones += (
            "Se incluyen dos fotos, una anterior y una actual de la misma planta: compara la "
            "evolución (mejor, igual o peor) y ténlo en cuenta en el veredicto, además del estado "
            "actual en sí.\n"
        )
    # El formato "chat.completions" de Groq/OpenAI mete texto e imagenes
    # como bloques dentro de un unico mensaje de usuario - maximo 3
    # imagenes por peticion (limite documentado de Groq), aqui como mucho
    # se mandan 2 (anterior + actual).
    content: list[dict] = [{"type": "text", "text": instrucciones}]
    if previous_photo is not None:
        prev_bytes, prev_content_type = previous_photo
        content.append({"type": "text", "text": "Foto anterior:"})
        content.append(_image_part(prev_bytes, prev_content_type))
        content.append({"type": "text", "text": "Foto actual:"})
    content.append(_image_part(photo_bytes, content_type))

    respuesta = _generate_with_retries(content)
    return _parse_respuesta(respuesta)


def _generate_with_retries(content: list[dict]) -> str:
    ultimo_error: Exception | None = None
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            completion = _client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": content}],
                max_completion_tokens=400,
            )
            return completion.choices[0].message.content
        except (groq.InternalServerError, groq.RateLimitError) as err:
            # Solo se reintenta un fallo del SERVIDOR o de limite de tasa
            # (ambos transitorios) - un error de cliente (clave invalida,
            # peticion mal formada) no se arregla reintentando, sube tal cual.
            ultimo_error = err
            if intento < MAX_INTENTOS:
                time.sleep(ESPERA_ENTRE_INTENTOS_S)
    raise ultimo_error
