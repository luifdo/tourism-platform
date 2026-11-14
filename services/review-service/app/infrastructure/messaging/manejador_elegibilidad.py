"""Traduce `reserva.finalizada` de la cola `review.elegibilidad` a su caso de uso."""

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.dto.visita_finalizada import VisitaFinalizada
from app.application.use_cases.registrar_visita import RegistrarVisita
from app.infrastructure.messaging.esquemas.reserva_finalizada_payload import (
    ReservaFinalizadaPayload,
)
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.evento_invalido import EventoInvalido

COLA = "review.elegibilidad"
CLAVES = ("reserva.finalizada",)


class ManejadorElegibilidad:
    def __init__(self, registrar: RegistrarVisita) -> None:
        self._registrar = registrar

    async def __call__(self, sobre: SobreEvento) -> ResultadoConsumo:
        if sobre.event_type not in CLAVES:
            raise EventoInvalido(f"{COLA} no maneja {sobre.event_type}")
        reserva = ReservaFinalizadaPayload.model_validate(sobre.payload)
        return await self._registrar.execute(
            VisitaFinalizada(
                event_id=sobre.event_id,
                turista_id=reserva.turista_id,
                servicio_id=reserva.servicio_id,
                fecha=reserva.fecha_reserva,
            )
        )
