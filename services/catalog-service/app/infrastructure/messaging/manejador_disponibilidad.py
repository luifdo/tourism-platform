"""Traduce `disponibilidad.actualizada` de la cola `catalog.disponibilidad` a su caso de uso."""

from app.application.dto.disponibilidad_recibida import DisponibilidadRecibida
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.aplicar_disponibilidad import AplicarDisponibilidad
from app.infrastructure.messaging.esquemas.disponibilidad_payload import DisponibilidadPayload
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.evento_invalido import EventoInvalido

COLA = "catalog.disponibilidad"
CLAVES = ("disponibilidad.actualizada",)


class ManejadorDisponibilidad:
    def __init__(self, aplicar: AplicarDisponibilidad) -> None:
        self._aplicar = aplicar

    async def __call__(self, sobre: SobreEvento) -> ResultadoConsumo:
        if sobre.event_type not in CLAVES:
            raise EventoInvalido(f"{COLA} no maneja {sobre.event_type}")
        dia = DisponibilidadPayload.model_validate(sobre.payload)
        return await self._aplicar.execute(
            DisponibilidadRecibida(
                event_id=sobre.event_id,
                servicio_id=dia.servicio_id,
                fecha=dia.fecha,
                cupos_totales=dia.cupos_totales,
                cupos_disponibles=dia.cupos_disponibles,
                version=dia.version,
            )
        )
