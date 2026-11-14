from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PrestadorSuspendidoPayload(BaseModel):
    """`contracts/events/prestador.suspendido.v1.json`."""

    model_config = ConfigDict(extra="ignore")

    prestador_id: UUID
    usuario_id: UUID
    suspendido_por: UUID
    motivo: str | None = Field(default=None, max_length=500)
