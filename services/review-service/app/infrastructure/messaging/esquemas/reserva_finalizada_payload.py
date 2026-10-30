from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReservaFinalizadaPayload(BaseModel):
    """Lo que review usa de `contracts/events/reserva.finalizada.v1.json`.

    El resto (reserva, prestador, personas) se ignora: review solo necesita saber quién
    visitó qué servicio y cuándo.
    """

    model_config = ConfigDict(extra="ignore")

    turista_id: UUID
    servicio_id: UUID
    fecha_reserva: date
