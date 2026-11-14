from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Protocol

from app.application.dto.estado_outbox import EstadoOutbox
from app.application.dto.evento_pendiente import EventoPendiente
from app.application.dto.resultado_lote import ResultadoLote


class OutboxPendiente(Protocol):
    """Lado del relay del outbox: tomar lo pendiente, publicarlo y marcarlo."""

    async def procesar_lote(
        self,
        limite: int,
        publicar: Callable[[EventoPendiente], Awaitable[None]],
        ahora: datetime,
    ) -> ResultadoLote:
        """Toma hasta `limite` eventos pendientes, en orden de creación, sin que otro relay
        pueda tomar los mismos (`FOR UPDATE SKIP LOCKED`); llama `publicar` con cada uno y
        marca `publicado_en` a los confirmados, en la misma transacción.

        Si `publicar` falla, suma un intento a ese evento y corta el lote: lo más probable es
        que el broker esté caído y los siguientes fallen igual. Lo ya confirmado queda marcado.
        """
        ...

    async def estado(self) -> EstadoOutbox: ...

    async def limpiar_publicados(self, antes_de: datetime) -> int:
        """Borra los eventos ya publicados antes de esa fecha; devuelve cuántos."""
        ...
