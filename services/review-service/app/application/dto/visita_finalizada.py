from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True, slots=True)
class VisitaFinalizada:
    """Una reserva finalizada (`reserva.finalizada`): habilita la reseña del turista."""

    event_id: UUID
    turista_id: UUID
    servicio_id: UUID
    fecha: date
