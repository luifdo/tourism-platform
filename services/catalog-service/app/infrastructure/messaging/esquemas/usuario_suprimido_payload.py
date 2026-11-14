from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UsuarioSuprimidoPayload(BaseModel):
    """`contracts/events/usuario.suprimido.v1.json`."""

    model_config = ConfigDict(extra="ignore")

    usuario_id: UUID
    rol: Literal["Turista", "Prestador", "Entidad", "Admin"]
