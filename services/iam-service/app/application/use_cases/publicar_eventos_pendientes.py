from collections.abc import Callable
from datetime import datetime

from app.application.dto.resultado_lote import ResultadoLote
from app.application.ports.outbox_pendiente import OutboxPendiente
from app.application.ports.publicador_eventos import PublicadorEventos


class PublicarEventosPendientes:
    """Relay del outbox (ADR-008, C-09): publica en RabbitMQ lo que se guardó con cada cambio.

    La entrega es "al menos una vez": si el proceso cae después de que el broker confirme y
    antes de marcar el evento, se publica otra vez. Los consumidores descartan duplicados
    por `event_id`.
    """

    def __init__(
        self,
        outbox: OutboxPendiente,
        publicador: PublicadorEventos,
        reloj: Callable[[], datetime],
        lote: int,
    ) -> None:
        self._outbox = outbox
        self._publicador = publicador
        self._reloj = reloj
        self._lote = lote

    async def execute(self) -> ResultadoLote:
        return await self._outbox.procesar_lote(
            self._lote, self._publicador.publicar, self._reloj()
        )
