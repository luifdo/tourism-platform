from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DisponibilidadPayload(BaseModel):
    """`contracts/events/disponibilidad.actualizada.v1.json`."""

    model_config = ConfigDict(extra="ignore")

    servicio_id: UUID
    fecha: date
    cupos_totales: int = Field(ge=0)
    cupos_disponibles: int = Field(ge=0)
    version: int = Field(ge=1)
