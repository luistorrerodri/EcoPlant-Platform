import logging
import time

import requests

logger = logging.getLogger("ecoplant.weather")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Umbral de probabilidad de lluvia (%) a partir del cual se pospone el
# riego automatico. Punto de partida, ajustable con el uso real.
RAIN_PROBABILITY_THRESHOLD = 50
# Ventana de horas futuras a consultar.
FORECAST_HOURS = 6
# TTL del cache en memoria de proceso - un unico worker de uvicorn, sin
# necesidad de nada compartido entre procesos.
CACHE_TTL_SECONDS = 45 * 60

_cache: dict[tuple[float, float], tuple[bool, float]] = {}


def get_rain_forecast(lat: float, lon: float) -> bool | None:
    """True si hay lluvia prevista en las proximas FORECAST_HOURS horas,
    False si no, None si no se pudo determinar (fallo de red, timeout,
    respuesta inesperada). None debe tratarse siempre como "no bloquear
    el riego" - un fallo de esta API no debe poder dejar una planta sin
    regar."""
    key = (round(lat, 2), round(lon, 2))
    cached = _cache.get(key)
    if cached is not None and time.time() - cached[1] < CACHE_TTL_SECONDS:
        return cached[0]

    try:
        response = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation_probability",
                "forecast_hours": FORECAST_HOURS,
            },
            timeout=5,
        )
        if not response.ok:
            logger.warning("Open-Meteo fallo (%s): %s", response.status_code, response.text)
            return None
        probabilities = response.json()["hourly"]["precipitation_probability"]
        value = max(probabilities) >= RAIN_PROBABILITY_THRESHOLD if probabilities else False
    except (requests.RequestException, KeyError, ValueError, TypeError):
        logger.exception("Error consultando Open-Meteo para (%s, %s)", lat, lon)
        return None

    _cache[key] = (value, time.time())
    return value
