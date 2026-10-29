from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResenaPayload(BaseModel):
    """Campos comunes a `contracts/events/resena.publicada.v1.json` y `resena.ocultada.v1.json`.

    Los propios de la ocultación (`moderada_por`, `motivo`) se ignoran.
    """

    model_config = ConfigDict(extra="ignore")

    resena_id: UUID
    servicio_id: UUID
    turista_id: UUID
    puntuacion: int = Field(ge=1, le=5)
