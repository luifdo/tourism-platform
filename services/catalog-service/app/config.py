from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio, cargada desde variables de entorno o un archivo .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "catalog-service"
    service_port: int = 8002
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+asyncpg://catalog_user:catalog_password@localhost:5434/catalog_db"
    )
    database_health_timeout_seconds: float = 2.0

    valkey_url: str = "redis://localhost:6380/0"
    valkey_timeout_seconds: float = 0.25

    rabbitmq_url: str = "amqp://guest:guest@localhost:5673/"
    rabbitmq_timeout_seconds: float = 5.0
    events_exchange: str = "turismo.eventos"

    # Relay del outbox (worker): lote por vuelta, pausa entre vueltas, espera máxima tras
    # fallos (crece al doble desde la pausa) y días que se guardan los eventos ya publicados.
    outbox_lote: int = 100
    outbox_intervalo_segundos: float = 1.0
    outbox_espera_maxima_segundos: float = 30.0
    outbox_retencion_dias: int = 7
    worker_metrics_port: int = 9102

    # Intención de visita: secreto del que sale la sal diaria del hash del IP. En producción
    # va en un Secret de Kubernetes; cambiarlo solo hace que hoy se cuente otra vez a todos.
    intencion_visita_secreto: str = "desarrollo-cambiar-en-produccion"

    # Correos de reservas (worker). Contacto de usuarios en iam por su ruta interna
    # (contracts/openapi/iam-interno.yaml); SMTP con STARTTLS en producción y Mailpit
    # (docker-compose.dev.yml) en desarrollo.
    iam_url_interna: str = "http://localhost:8001"
    iam_timeout_seconds: float = 3.0
    smtp_host: str = "localhost"
    smtp_port: int = 1026
    smtp_usuario: str = ""
    smtp_clave: str = ""
    smtp_starttls: bool = False
    smtp_timeout_seconds: float = 10.0
    smtp_remitente: str = "Turismo Santa Marta <no-responder@turismo-santamarta.local>"
    # Mensajes que cada consumidor procesa a la vez (prefetch de RabbitMQ).
    consumidor_prefetch: int = 10

    # Imágenes del catálogo en SeaweedFS (API S3). El endpoint es el público: la URL firmada
    # la usa el navegador y la firma incluye el host.
    s3_endpoint_publico: str = "http://localhost:8333"
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket_imagenes: str = "catalogo-imagenes"
    imagenes_url_publica: str = "http://localhost:8333/catalogo-imagenes"

    # Nominatim (OpenStreetMap): su política exige un User-Agent que identifique la app.
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "turismo-santa-marta-catalog-service/0.1"
    nominatim_email: str | None = None
    nominatim_timeout_seconds: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
