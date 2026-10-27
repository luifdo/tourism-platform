from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PrestadorAprobadoPayload(BaseModel):
    """`contracts/events/prestador.aprobado.v1.json`."""

    model_config = ConfigDict(extra="ignore")

    prestador_id: UUID
    usuario_id: UUID
    aprobado_por: UUID
    razon_social: str | None = None
