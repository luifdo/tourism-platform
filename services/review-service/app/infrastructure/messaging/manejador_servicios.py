"""Traduce `servicio.publicado` de la cola `review.servicios` a su caso de uso."""

from app.application.dto.dueno_publicado import DuenoPublicado
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.registrar_dueno_servicio import RegistrarDuenoServicio
from app.infrastructure.messaging.esquemas.servicio_publicado_payload import (
    ServicioPublicadoPayload,
)
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.evento_invalido import EventoInvalido

COLA = "review.servicios"
CLAVES = ("servicio.publicado",)


class ManejadorServicios:
    def __init__(self, registrar: RegistrarDuenoServicio) -> None:
        self._registrar = registrar

    async def __call__(self, sobre: SobreEvento) -> ResultadoConsumo:
        if sobre.event_type not in CLAVES:
            raise EventoInvalido(f"{COLA} no maneja {sobre.event_type}")
        servicio = ServicioPublicadoPayload.model_validate(sobre.payload)
        return await self._registrar.execute(
            DuenoPublicado(
                event_id=sobre.event_id,
                servicio_id=servicio.servicio_id,
                prestador_usuario_id=servicio.prestador_usuario_id,
                version=servicio.version,
            )
        )
