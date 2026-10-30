from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio, cargada desde variables de entorno o un archivo .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "iam-service"
    service_port: int = 8001
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://iam_user:iam_password@localhost:5433/iam_db"
    database_health_timeout_seconds: float = 2.0
    # Rol con el que se conecta la app; la migración inicial le revoca UPDATE/DELETE/TRUNCATE
    # sobre bitacora_auditoria.
    db_app_role: str = "iam_user"

    valkey_url: str = "redis://localhost:6379/0"
    valkey_health_timeout_seconds: float = 2.0

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    events_exchange: str = "turismo.eventos"
    rabbitmq_timeout_seconds: float = 5.0
    consumidor_prefetch: int = 10
    # Tope de la espera creciente con la que el worker reintenta conectarse a RabbitMQ.
    rabbitmq_espera_maxima_segundos: float = 30.0
    # Relay del outbox (worker, C-09): lote por vuelta, pausa entre vueltas, espera máxima tras
    # un fallo y días que se conservan los eventos ya publicados. Mismos valores que catalog.
    outbox_lote: int = 100
    outbox_intervalo_segundos: float = 1.0
    outbox_espera_maxima_segundos: float = 30.0
    outbox_retencion_dias: int = 7

    # Worker (python -m app.worker): /metrics, que también sirve de sonda de vida.
    worker_metrics_port: int = 9101
    log_level: str = "INFO"

    # SeaweedFS (C-30). El interno sube los documentos; el público firma las URL que abre el
    # navegador del Admin. Las credenciales de desarrollo sirven porque el SeaweedFS de
    # docker-compose.dev.yml no tiene archivo de identidades; en k3s las provee infra/ (C-46).
    s3_endpoint_url: str = "http://localhost:8333"
    s3_endpoint_publico: str = "http://localhost:8333"
    s3_region: str = "us-east-1"
    s3_access_key: str = "iam_access_dev"
    s3_secret_key: str = "iam_secret_dev"
    s3_bucket: str = "documentos-verificacion"

    # Correo de recuperación (C-28). En desarrollo, Mailpit de docker-compose.dev.yml; en k3s,
    # el usuario y la contraseña van en un Secret y smtp_tls=true (STARTTLS).
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "Turismo Santa Marta <no-responder@turismo-santamarta.local>"
    smtp_usuario: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False
    smtp_timeout_seconds: float = 10.0
    # Base del enlace del correo: de aquí y nunca del Host de la petición, que lo elige el cliente.
    pwa_url: str = "http://localhost:5173"

    jwt_algorithm: str = "RS256"
    jwt_issuer: str = "iam-service"
    jwt_private_key_path: Path = Path("keys/private.pem")
    jwt_public_key_path: Path = Path("keys/public.pem")
    jwt_access_token_ttl_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
