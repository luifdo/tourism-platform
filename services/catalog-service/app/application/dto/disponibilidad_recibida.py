from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DisponibilidadRecibida:
    """`disponibilidad.actualizada.v1` de booking-service, ya validado."""

    event_id: UUID
    servicio_id: UUID
    fecha: date
    cupos_totales: int
    cupos_disponibles: int
    version: int
