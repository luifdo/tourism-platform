from pydantic_settings import BaseSettings


class Configuracion(BaseSettings):
    """Variables de entorno del servicio. En el compose llegan desde .env.

    Los valores por defecto sirven para correr el servicio fuera de Docker contra los
    puertos que publica docker-compose.yml.
    """

    db_url: str = "postgresql+psycopg://turismo:turismo@localhost:5434/recommendation_db"
    valkey_url: str = "redis://localhost:6380/0"
