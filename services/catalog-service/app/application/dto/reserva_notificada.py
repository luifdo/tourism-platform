from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.domain.entities.reserva_proyeccion import TipoEventoReserva
from app.domain.value_objects.identidad import Rol


@dataclass(frozen=True, slots=True)
class ReservaNotificada:
    """Evento `reserva.*` con los campos que necesitan los correos (contracts/events/)."""

    event_id: UUID
    tipo: TipoEventoReserva
    reserva_id: UUID
    servicio_id: UUID
    turista_id: UUID
    fecha_reserva: date
    numero_personas: int
    motivo: str | None = None  # rechazada, cancelada
    cancelada_por: Rol | None = None  # cancelada: Turista o Prestador
    fecha_anterior: date | None = None  # modificada
    numero_personas_anterior: int | None = None  # modificada
    expira_en: datetime | None = None  # modificada
