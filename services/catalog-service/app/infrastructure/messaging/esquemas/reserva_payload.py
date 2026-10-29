from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReservaPayload(BaseModel):
    """Campos comunes a los seis `contracts/events/reserva.*.v1.json` que usa la proyección.

    Los propios de cada evento (`motivo`, `cancelada_por`, `fecha_anterior`, `expira_en`) se
    ignoran: a la demanda le basta el estado final de la reserva.
    """

    model_config = ConfigDict(extra="ignore")

    reserva_id: UUID
    servicio_id: UUID
    turista_id: UUID
    prestador_id: UUID
    fecha_reserva: date
    numero_personas: int = Field(ge=1)
