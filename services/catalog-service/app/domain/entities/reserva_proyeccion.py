from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from app.domain.value_objects.catalogos import EstadoReserva


class TipoEventoReserva(StrEnum):
    SOLICITADA = "reserva.solicitada"
    MODIFICADA = "reserva.modificada"
    CONFIRMADA = "reserva.confirmada"
    RECHAZADA = "reserva.rechazada"
    CANCELADA = "reserva.cancelada"
    FINALIZADA = "reserva.finalizada"

    @property
    def estado_resultante(self) -> EstadoReserva:
        # Una modificación solo ocurre en SOLICITADA (UC12) y no cambia el estado.
        if self is TipoEventoReserva.MODIFICADA:
            return EstadoReserva.SOLICITADA
        return EstadoReserva(self.name)


@dataclass(frozen=True, slots=True)
class EventoReserva:
    """Datos de un evento `reserva.*` que necesita la proyección (ya validado contra su esquema)."""

    tipo: TipoEventoReserva
    reserva_id: UUID
    servicio_id: UUID
    prestador_id: UUID
    turista_id: UUID
    fecha_reserva: date
    numero_personas: int
    ocurrido_en: datetime


@dataclass(kw_only=True)
class ReservaProyeccion:
    """Estado actual de una reserva, visto desde catalog-service.

    Se guarda el estado y no contadores: los eventos pueden llegar repetidos o desordenados
    (reintentos, DLQ) y solo se aplica uno si ocurrió después del último aplicado. La
    demanda y la saturación se calculan agregando esta tabla.
    """

    reserva_id: UUID
    servicio_id: UUID
    prestador_id: UUID
    turista_id: UUID
    fecha_reserva: date
    numero_personas: int
    estado: EstadoReserva
    ultimo_evento_en: datetime

    @classmethod
    def desde_evento(cls, evento: EventoReserva) -> "ReservaProyeccion":
        return cls(
            reserva_id=evento.reserva_id,
            servicio_id=evento.servicio_id,
            prestador_id=evento.prestador_id,
            turista_id=evento.turista_id,
            fecha_reserva=evento.fecha_reserva,
            numero_personas=evento.numero_personas,
            estado=evento.tipo.estado_resultante,
            ultimo_evento_en=evento.ocurrido_en,
        )

    def aplicar(self, evento: EventoReserva) -> bool:
        """Devuelve True si el evento cambió la proyección; False si era viejo o repetido."""
        if evento.ocurrido_en <= self.ultimo_evento_en:
            return False
        self.fecha_reserva = evento.fecha_reserva
        self.numero_personas = evento.numero_personas
        self.estado = evento.tipo.estado_resultante
        self.ultimo_evento_en = evento.ocurrido_en
        return True

    @property
    def activa(self) -> bool:
        return self.estado.activa
