import logging
from uuid import UUID

from app.application.ports.contador_intenciones import ContadorIntenciones
from app.application.ports.deduplicador_visitas import DeduplicadorVisitas
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj

logger = logging.getLogger(__name__)


class RegistrarIntencionVisita:
    """El turista pidió "Cómo llegar" a un servicio: cuenta una vez por visitante, servicio y día.

    Es un indicador aparte de la saturación (una intención no es una reserva). Si Valkey no
    responde, se cuenta igual: es mejor contar de más durante una caída que perder el dato.
    """

    def __init__(
        self, deduplicador: DeduplicadorVisitas, contador: ContadorIntenciones, reloj: Reloj
    ) -> None:
        self._deduplicador = deduplicador
        self._contador = contador
        self._reloj = reloj

    async def execute(self, servicio_id: UUID, ip: str | None) -> None:
        hoy = self._reloj.hoy()
        primera = await self._deduplicador.primera_vez(ip, servicio_id, hoy) if ip else None
        if primera is False:
            return  # ya contó hoy
        if primera is None:
            logger.warning("Intención de visita sin descarte de repetidos (sin IP o sin Valkey)")
        if not await self._contador.sumar(servicio_id, hoy):
            if primera and ip:
                await self._deduplicador.olvidar(ip, servicio_id, hoy)
            raise NoEncontrado(recurso="servicio", id=str(servicio_id))
