from app.application.dto.resultado_lote import ResultadoLote
from app.application.ports.outbox_pendiente import OutboxPendiente
from app.application.ports.publicador_eventos import PublicadorEventos
from app.domain.ports.reloj import Reloj


class PublicarEventosPendientes:
    """Relay del outbox (ADR-008): publica en RabbitMQ lo que se guardó con cada cambio.

    La entrega es "al menos una vez": si el proceso cae después de que el broker confirme y
    antes de marcar el evento, se publica otra vez. Los consumidores descartan duplicados
    por `event_id`.
    """

    def __init__(
        self, outbox: OutboxPendiente, publicador: PublicadorEventos, reloj: Reloj, lote: int
    ) -> None:
        self._outbox = outbox
        self._publicador = publicador
        self._reloj = reloj
        self._lote = lote

    async def execute(self) -> ResultadoLote:
        return await self._outbox.procesar_lote(
            self._lote, self._publicador.publicar, self._reloj.ahora()
        )
