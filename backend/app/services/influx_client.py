from influxdb_client import InfluxDBClient

from app.config import settings

_client = InfluxDBClient(
    url=settings.influxdb_url, token=settings.influxdb_token, org=settings.influxdb_org
)
_query_api = _client.query_api()

# No todos los dispositivos publican todos estos campos (depende del
# sensor de ambiente que lleve cada uno - ver firmware/README.md): la
# consulta de un campo que un dispositivo concreto nunca publica
# simplemente no devuelve puntos para el, sin error, misma logica que
# ya aplicaba a temp_suelo cuando el DS18B20 no estaba conectado.
NUMERIC_FIELDS = ["humedad_suelo", "temp_aire", "presion", "temp_suelo", "humedad_ambiente"]

# Rango fisicamente plausible por campo - una lectura fuera de este
# rango es un fallo de lectura del sensor (p.ej. un DHT22 devolviendo
# ~121 tras un error de bus), nunca un dato real, y se descarta en la
# propia consulta Flux para que ni siquiera entre en un mean()/min()/max()
# - sin esto, un solo valor disparatado desvirtua el rango completo que
# ve el resumen de salud y el diagnostico con IA. humedad_suelo_raw (la
# lectura ADC sin convertir, usada solo para calibrar) se deja fuera a
# proposito: ahi los valores "extremos" son precisamente el dato real
# que se quiere capturar.
PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    "humedad_suelo": (0, 100),
    "temp_aire": (-10, 60),
    "presion": (800, 1100),
    "temp_suelo": (-10, 60),
    "humedad_ambiente": (0, 100),
}


def _rango_flux(field: str) -> str:
    # Linea de filtro Flux adicional para el rango plausible del campo,
    # o cadena vacia si no aplica (p.ej. humedad_suelo_raw).
    rango = PLAUSIBLE_RANGES.get(field)
    if rango is None:
        return ""
    minimo, maximo = rango
    return f"|> filter(fn: (r) => r._value >= {minimo} and r._value <= {maximo})\n          "


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
          {_rango_flux(field)}|> aggregateWindow(every: {window}, fn: mean, createEmpty: false)
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


def get_latest_value(device_id: str, field: str) -> float | None:
    # Consulta puntual sin aggregateWindow, para capturar "lo que marca
    # el sensor ahora mismo" (p.ej. al calibrar) - get_readings() agrega
    # a 1m/10m/1h segun el rango, demasiado impreciso para esto. El
    # dispositivo publica cada 4s, asi que 30s de margen basta.
    flux = f'''
    from(bucket: "{settings.influxdb_bucket}")
      |> range(start: -30s)
      |> filter(fn: (r) => r._measurement == "sensores")
      |> filter(fn: (r) => r._field == "{field}")
      |> filter(fn: (r) => r.device_id == "{device_id}")
      {_rango_flux(field)}|> last()
    '''
    tables = _query_api.query(flux)
    for table in tables:
        for record in table.records:
            return record.get_value()
    return None
