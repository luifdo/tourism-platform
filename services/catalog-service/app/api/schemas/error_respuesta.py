from pydantic import BaseModel


class ErrorRespuesta(BaseModel):
    """Formato común de error de la plataforma (contrato `Error`)."""

    error: str
    message: str
    correlation_id: str | None
