# Backend API

API multiusuario (FastAPI + PostgreSQL) para EcoPlant Platform: registro/login, ubicaciones, y reclamación/control de dispositivos. Es una pieza nueva y aditiva — Node-RED sigue orquestando el riego y sirviendo su propio dashboard en `/ui`; este servicio añade la capa de usuarios y permisos por delante, sin sustituir nada. Detalle de las decisiones de diseño en [`../docs/architecture.md`](../docs/architecture.md#backend-multiusuario).

## Requisitos

- Python 3.11+
- PostgreSQL 15 (accesible, con una base de datos y un usuario ya creados — ver [`../platform/README.md`](../platform/README.md#6-backend-api))
- El resto de la plataforma corriendo: Mosquitto (mTLS) e InfluxDB, para los endpoints de riego y lecturas

## Configuración

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Rellena `.env`:

| Variable | Qué es |
|---|---|
| `DATABASE_URL` | Cadena de conexión a PostgreSQL (`postgresql+psycopg2://usuario:contraseña@host:5432/bd`) |
| `JWT_SECRET_KEY` | Clave para firmar los tokens de acceso. Genera una con `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` — nunca reutilizar la de ejemplo |
| `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Parámetros del esquema de tokens (ver "Autenticación con tokens revocables" en `docs/architecture.md`) |
| `INTERNAL_API_TOKEN` | Token compartido para `/api/internal/*` (lo usa Node-RED, no un usuario). Genera uno con `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `MQTT_HOST`, `MQTT_PORT` | Dirección del broker Mosquitto |
| `MQTT_CA_CERT_PATH` | CA que firmó el certificado del broker (la misma que usa Node-RED) |
| `MQTT_CLIENT_CERT_PATH`, `MQTT_CLIENT_KEY_PATH` | Certificado de cliente propio del backend (CN `backend-api`), generado siguiendo el mismo procedimiento que `nodered`/`macetero01` |
| `INFLUXDB_URL`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET` | Igual que el resto de la plataforma |
| `INFLUXDB_TOKEN` | Token de **solo lectura**, distinto del que usa Node-RED (que tiene escritura) |

`.env` está en `.gitignore` y no debe subirse al repositorio.

## Base de datos

```bash
alembic upgrade head
```

Para generar una migración nueva tras cambiar los modelos en `app/models/`:

```bash
alembic revision --autogenerate -m "descripción del cambio"
alembic upgrade head
```

**Importante**: los archivos de migración (`alembic/versions/*.py`) se generan localmente y hay que comitearlos al repositorio — Alembic no los regenera solo, y sin ellos `alembic upgrade head` no tiene nada que aplicar en una instalación nueva.

## Arrancar

En desarrollo (recarga automática al cambiar el código):

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

En producción, como servicio systemd — ver [`../platform/README.md`](../platform/README.md#6-backend-api).

Documentación interactiva (Swagger) en `http://127.0.0.1:8000/api/docs`.

## Estructura del proyecto

```
backend/
├── app/
│   ├── main.py        # instancia de FastAPI, routers, ciclo de vida MQTT
│   ├── config.py       # configuración (lee .env)
│   ├── database.py     # conexión SQLAlchemy
│   ├── security.py     # hash de contraseñas/códigos, JWT
│   ├── deps.py          # dependencias de autenticación (get_current_user, get_current_admin)
│   ├── models/          # tablas SQLAlchemy (User, Location, Device, PlantType, RefreshToken)
│   ├── schemas/         # modelos Pydantic de entrada/salida
│   ├── routers/         # endpoints (auth, locations, devices, plant_types, internal, admin)
│   └── services/        # clientes de MQTT e InfluxDB
├── alembic/              # migraciones de base de datos
└── scripts/              # utilidades de línea de comandos
```

## Modelo de permisos

No existe ningún endpoint para autopromocionarse a administrador — es intencional. Para dar de alta el primer admin, hazlo directamente en la base de datos:

```sql
UPDATE users SET is_admin = true WHERE email = 'tu@email.com';
```

Solo un admin puede sembrar dispositivos nuevos (`POST /api/admin/devices/seed`) y rotar códigos de reclamación (`POST /api/admin/devices/{device_id}/rotate-claim-code`).

## Verificación

```bash
curl http://127.0.0.1:8000/api/health
```

Debe devolver `{"status":"ok"}`. Para probar el flujo completo, usa el Swagger (`/api/docs`):

1. `POST /api/auth/register` → cuenta activa al momento, devuelve tokens
2. Con un usuario `is_admin`: `POST /api/admin/devices/seed` → guarda el `claim_code` (solo se muestra una vez)
3. `POST /api/locations` → crea una ubicación propia
4. `POST /api/devices/claim` → engancha el dispositivo sembrado a esa ubicación
5. `GET /api/devices/{device_id}/readings` → histórico agregado desde InfluxDB
6. `POST /api/devices/{device_id}/water` → publica el comando de riego por MQTT

## Notas

- El arranque del servicio no depende de que Mosquitto esté disponible en ese instante: la conexión MQTT es asíncrona (`connect_async` + `loop_start`) y reintenta sola en segundo plano.
- Las contraseñas y códigos de reclamación se hashean con `passlib[bcrypt]`. Esa librería no es compatible con `bcrypt>=4.1` (`requirements.txt` fija `bcrypt==4.0.1` a propósito — ver [`../docs/troubleshooting.md`](../docs/troubleshooting.md#16-passlib-no-es-compatible-con-las-versiones-recientes-de-bcrypt)).
- Las consultas a InfluxDB agregan (`aggregateWindow`) según el rango pedido — sin esto, 24h de lecturas del ESP32 (una cada 4s) son ~21.600 puntos por campo, demasiado para cualquier cliente razonable.
