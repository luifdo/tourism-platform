"""Traduce los eventos `reserva.*` de la cola `catalog.demanda` a su caso de uso."""

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.aplicar_evento_reserva import AplicarEventoReserva
from app.domain.entities.reserva_proyeccion import EventoReserva, TipoEventoReserva
from app.infrastructure.messaging.esquemas.reserva_payload import ReservaPayload
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.evento_invalido import EventoInvalido

COLA = "catalog.demanda"
CLAVES = tuple(t.value for t in TipoEventoReserva)


class ManejadorDemanda:
    def __init__(self, aplicar: AplicarEventoReserva) -> None:
        self._aplicar = aplicar

    async def __call__(self, sobre: SobreEvento) -> ResultadoConsumo:
        try:
            tipo = TipoEventoReserva(sobre.event_type)
        except ValueError as exc:
            raise EventoInvalido(f"{COLA} no maneja {sobre.event_type}") from exc
        reserva = ReservaPayload.model_validate(sobre.payload)
        evento = EventoReserva(
            tipo=tipo,
            reserva_id=reserva.reserva_id,
            servicio_id=reserva.servicio_id,
            prestador_id=reserva.prestador_id,
            turista_id=reserva.turista_id,
            fecha_reserva=reserva.fecha_reserva,
            numero_personas=reserva.numero_personas,
            ocurrido_en=sobre.occurred_at,
        )
        return await self._aplicar.execute(sobre.event_id, evento)
