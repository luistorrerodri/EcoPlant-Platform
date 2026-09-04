from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Token compartido para /api/internal/* (lo llama Node-RED, no un
    # usuario con sesión). Trafico solo por loopback, pero igualmente
    # protegido con este secreto - ver app/deps.py:verify_internal_token.
    internal_api_token: str

    mqtt_host: str
    mqtt_port: int = 8883
    mqtt_ca_cert_path: str
    mqtt_client_cert_path: str
    mqtt_client_key_path: str

    influxdb_url: str
    influxdb_org: str
    influxdb_bucket: str
    influxdb_token: str


settings = Settings()
