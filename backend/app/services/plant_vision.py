from datetime import datetime, timedelta, timezone

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.config import settings
from app.models.device import Device
from app.models.watering_event import WateringEvent
from app.services import influx_client

WINDOW_HOURS = 120  # 5 dias, mismo contexto que pidio Luis
MODEL = "gemini-flash-latest"  # alias que Google mantiene apuntando al Flash mas reciente - nivel gratuito

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

    response = _client.models.generate_content(model=MODEL, contents=contents)
    return _parse_respuesta(response.text)
