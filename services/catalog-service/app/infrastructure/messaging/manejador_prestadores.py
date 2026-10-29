"""Traduce los eventos de iam de la cola `catalog.prestadores` a sus casos de uso."""

from app.application.dto.prestador_aprobado_recibido import PrestadorAprobadoRecibido
from app.application.dto.prestador_suspendido_recibido import PrestadorSuspendidoRecibido
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.aplicar_prestador_aprobado import AplicarPrestadorAprobado
from app.application.use_cases.aplicar_prestador_suspendido import AplicarPrestadorSuspendido
from app.infrastructure.messaging.esquemas.prestador_aprobado_payload import (
    PrestadorAprobadoPayload,
)
from app.infrastructure.messaging.esquemas.prestador_suspendido_payload import (
    PrestadorSuspendidoPayload,
)
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.evento_invalido import EventoInvalido

COLA = "catalog.prestadores"
CLAVES = ("prestador.aprobado", "prestador.suspendido")


class ManejadorPrestadores:
    def __init__(
        self, aprobado: AplicarPrestadorAprobado, suspendido: AplicarPrestadorSuspendido
    ) -> None:
        self._aprobado = aprobado
        self._suspendido = suspendido

    async def __call__(self, sobre: SobreEvento) -> ResultadoConsumo:
        if sobre.event_type == "prestador.aprobado":
            aprobado = PrestadorAprobadoPayload.model_validate(sobre.payload)
            return await self._aprobado.execute(
                PrestadorAprobadoRecibido(
                    event_id=sobre.event_id,
                    ocurrido_en=sobre.occurred_at,
                    prestador_id=aprobado.prestador_id,
                    usuario_id=aprobado.usuario_id,
                    razon_social=aprobado.razon_social,
                )
            )
        if sobre.event_type == "prestador.suspendido":
            suspendido = PrestadorSuspendidoPayload.model_validate(sobre.payload)
            return await self._suspendido.execute(
                PrestadorSuspendidoRecibido(
                    event_id=sobre.event_id,
                    ocurrido_en=sobre.occurred_at,
                    prestador_id=suspendido.prestador_id,
                    usuario_id=suspendido.usuario_id,
                )
            )
        raise EventoInvalido(f"{COLA} no maneja {sobre.event_type}")
