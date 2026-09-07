from influxdb_client import InfluxDBClient

from app.config import settings

_client = InfluxDBClient(
    url=settings.influxdb_url, token=settings.influxdb_token, org=settings.influxdb_org
)
_query_api = _client.query_api()

NUMERIC_FIELDS = ["humedad_suelo", "temp_aire", "presion", "temp_suelo"]


def _aggregate_window(hours: int) -> str:
    # El ESP32 publica cada 4s: sin agregar, 24h son ~21.600 puntos
    # por campo, demasiado para pintar en un grafico o una respuesta
    # de API. Se reduce la resolucion segun el rango pedido.
    if hours <= 6:
        return "1m"
    if hours <= 48:
        return "10m"
    return "1h"


def get_readings(device_id: str, hours: int) -> dict:
    # Mismo patron de filtros que ya usa el resto del repo
    # (_measurement -> _field -> device_id), uno por campo numerico
    # para no mezclar escalas distintas en la misma serie.
    window = _aggregate_window(hours)
    points: list[dict] = []
    for field in NUMERIC_FIELDS:
        flux = f'''
        from(bucket: "{settings.influxdb_bucket}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r._measurement == "sensores")
          |> filter(fn: (r) => r._field == "{field}")
          |> filter(fn: (r) => r.device_id == "{device_id}")
          |> aggregateWindow(every: {window}, fn: mean, createEmpty: false)
        '''
        tables = _query_api.query(flux)
        for table in tables:
            for record in table.records:
                points.append(
                    {"time": record.get_time(), "field": field, "value": record.get_value()}
                )

    # "estado" es un campo de texto: no se puede agregar con las
    # mismas funciones que los numericos (ver docs/troubleshooting.md
    # #8), se consulta aparte con last().
    estado_flux = f'''
    from(bucket: "{settings.influxdb_bucket}")
      |> range(start: -{hours}h)
      |> filter(fn: (r) => r._measurement == "sensores")
      |> filter(fn: (r) => r._field == "estado")
      |> filter(fn: (r) => r.device_id == "{device_id}")
      |> last()
    '''
    estado_tables = _query_api.query(estado_flux)
    latest_estado = None
    for table in estado_tables:
        for record in table.records:
            latest_estado = record.get_value()

    return {"device_id": device_id, "latest_estado": latest_estado, "points": points}
