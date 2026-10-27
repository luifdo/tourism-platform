"""Configuración por variables de entorno (ver .env.example)."""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "booking-service"
    service_port: int = 8003
    log_level: str = "INFO"
    # "memoria": sin Postgres ni RabbitMQ (pruebas y demo). "postgres": booking_db real.
    modo_persistencia: Literal["memoria", "postgres"] = "memoria"
    plazo_respuesta_horas: int = 48
    # Solo en modo memoria: carga un servicio de ejemplo y habilita las rutas /dev para la demo.
    datos_demo: bool = True

    # ---------- Postgres (booking_db) ----------
    # Driver asíncrono asyncpg: con uno síncrono, cada consulta bloquearía todo el servidor.
    # El puerto 5433 local evita chocar con un Postgres instalado en el PC (5432).
    database_url: str = "postgresql+asyncpg://booking:booking@127.0.0.1:5433/booking_db"
    # Conexiones abiertas que se reutilizan entre peticiones (por réplica).
    db_pool_tamano: int = 10
    # Conexiones extra que se abren en un pico y se cierran después.
    db_pool_extra: int = 5
    # Segundos que una petición espera una conexión libre antes de fallar.
    db_pool_espera_s: float = 5.0

    # ---------- RabbitMQ (solo en modo postgres) ----------
    # Local: el contenedor de pruebas (scripts/rabbitmq_pruebas.py) en el puerto 5673.
    rabbitmq_url: str = "amqp://booking:booking@127.0.0.1:5673/"
    events_exchange: str = "turismo.eventos"
    # Relay del outbox: cuántos eventos publica por transacción y cuánto espera si no hay pendientes.
    relay_lote: int = 100
    relay_espera_s: float = 1.0

    @field_validator("database_url")
    @classmethod
    def _driver_asincrono(cls, url: str) -> str:
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL debe usar el driver asíncrono: postgresql+asyncpg://...")
        return url
