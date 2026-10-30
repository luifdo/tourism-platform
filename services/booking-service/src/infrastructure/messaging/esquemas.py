"""Validación de los eventos que booking consume (contracts/events)."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ServicioPublicado(BaseModel):
    """Payload de `servicio.publicado.v1` (contracts/events/servicio.publicado.v1.json)."""

    model_config = ConfigDict(extra="forbid")  # additionalProperties: false

    servicio_id: UUID
    prestador_id: UUID = Field(description="Perfil del prestador en el catálogo.")
    prestador_usuario_id: UUID = Field(description="Usuario del prestador en iam (su X-Usuario-Id).")
    capacidad_aforo_diario: int = Field(ge=1)
    tarifa_base: Decimal = Field(ge=0)
    activo: bool
    version: int = Field(ge=1)
