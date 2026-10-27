from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReservaNotificacionPayload(BaseModel):
    """Campos de los `contracts/events/reserva.*.v1.json` que usan los correos.

    Los propios de cada evento son opcionales: `motivo` (rechazada, cancelada),
    `cancelada_por` (cancelada), `fecha_anterior`, `numero_personas_anterior` y `expira_en`
    (modificada).
    """

    model_config = ConfigDict(extra="ignore")

    reserva_id: UUID
    servicio_id: UUID
    turista_id: UUID
    fecha_reserva: date
    numero_personas: int = Field(ge=1)
    motivo: str | None = None
    cancelada_por: Literal["Turista", "Prestador"] | None = None  # quién canceló (rol)
    fecha_anterior: date | None = None
    numero_personas_anterior: int | None = Field(default=None, ge=1)
    expira_en: datetime | None = None
