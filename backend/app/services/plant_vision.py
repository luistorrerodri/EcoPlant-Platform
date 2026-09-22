import time
from datetime import datetime, timedelta, timezone

from google import genai
from google.genai import errors, types
from sqlalchemy.orm import Session

from app.config import settings
from app.models.device import Device
from app.models.watering_event import WateringEvent
from app.services import influx_client

WINDOW_HOURS = 120  # 5 dias, mismo contexto que pidio Luis
MODEL = "gemini-3.5-flash-lite"  # confirmado en produccion: el alias "gemini-flash-latest" (el modelo
# insignia mas nuevo, al que apunta todo el mundo por defecto en el nivel gratuito) estaba saturado de
# forma sostenida (5 intentos repartidos en 15 minutos, todos 503). Un modelo "lite" concreto, mas barato
# de servir y con menos gente apuntandole por nombre, tiene mucha mas capacidad libre - de sobra para
# valorar una foto, no hace falta el modelo mas potente para esto.

# El nivel gratuito comparte capacidad con todo el mundo - un 503 "high
# demand" es un contratiempo esperado, no un fallo real (confirmado en
# produccion: dos intentos seguidos con el mismo 503). Reintentar unas
# pocas veces con espera absorbe eso sin que el usuario tenga que
# volver a pulsar el boton el mismo a mano.
MAX_INTENTOS = 3
ESPERA_ENTRE_INTENTOS_S = 5

_client = genai.Client(api_key=settings.gemini_api_key)

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
        raise ValueError(f"Respuesta de Gemini sin veredicto reconocible: {texto[:200]!r}")
    return verdict, resto.strip()


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
    instrucciones += f"\nDatos de los sensores:\n{contexto}"

    # contents mezcla texto y objetos Part (imagen) en la misma lista - asi
    # espera el SDK de google-genai las peticiones multimodales, ver
    # types.Part.from_bytes en la doc del SDK (googleapis/python-genai).
    contents: list = []
    if previous_photo is not None:
        prev_bytes, prev_content_type = previous_photo
        contents.append("Foto anterior:")
        contents.append(types.Part.from_bytes(data=prev_bytes, mime_type=prev_content_type))
        contents.append("Foto actual:")
    contents.append(types.Part.from_bytes(data=photo_bytes, mime_type=content_type))
    contents.append(instrucciones)

    response = _generate_with_retries(contents)
    return _parse_respuesta(response.text)


def _generate_with_retries(contents: list):
    ultimo_error: errors.ServerError | None = None
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            return _client.models.generate_content(model=MODEL, contents=contents)
        except errors.ServerError as err:
            # Solo se reintenta un fallo del SERVIDOR de Gemini (sobrecarga,
            # 503...) - un ClientError (clave invalida, peticion mal
            # formada) no se arregla reintentando, se deja subir tal cual.
            ultimo_error = err
            if intento < MAX_INTENTOS:
                time.sleep(ESPERA_ENTRE_INTENTOS_S)
    raise ultimo_error
