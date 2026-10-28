from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio, cargada desde variables de entorno o un archivo .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "review-service"
    service_port: int = 8004
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://review_user:review_password@localhost:5435/review_db"
    database_health_timeout_seconds: float = 2.0

    rabbitmq_url: str = "amqp://guest:guest@localhost:5674/"
    rabbitmq_timeout_seconds: float = 5.0
    events_exchange: str = "turismo.eventos"

    # Relay del outbox (worker): lote por vuelta, pausa entre vueltas, espera máxima tras
    # fallos (crece al doble desde la pausa) y días que se guardan los eventos ya publicados.
    outbox_lote: int = 100
    outbox_intervalo_segundos: float = 1.0
    outbox_espera_maxima_segundos: float = 30.0
    outbox_retencion_dias: int = 7
    worker_metrics_port: int = 9104
    # Mensajes que cada consumidor procesa a la vez (prefetch de RabbitMQ).
    consumidor_prefetch: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
