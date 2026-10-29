from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Configuracion(BaseSettings):
    """Variables de entorno del servicio. En el compose llegan desde .env.

    Los valores por defecto sirven para correr el servicio fuera de Docker contra los
    puertos que publica docker-compose.yml.
    """

    db_url: str = "postgresql+psycopg://turismo:turismo@localhost:5434/recommendation_db"
    valkey_url: str = "redis://localhost:6380/0"

    # Servicios que consultan las tools (en el compose, el mock-plataforma).
    catalog_url: str = "http://localhost:9000/api/catalog"
    booking_url: str = "http://localhost:9000/api/bookings"
    review_url: str = "http://localhost:9000/api/reviews"
    herramientas_timeout_segundos: float = 5.0

    # Proveedor de IA (Fase 5). Sin proveedor, el chat responde 503.
    llm_provider: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    # Tiempo máximo de una consulta completa al chat (modelo + tools).
    chat_timeout_segundos: float = 45.0
    # Límite de mensajes por turista: cuida la cuota del proveedor y evita abusos.
    chat_limite_mensajes: int = 10
    chat_limite_ventana_segundos: int = 300
