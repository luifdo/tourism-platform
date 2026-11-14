"""Puerto `Outbox` (ADR-008, C-09): el evento se guarda en la misma transacción que el cambio.

Si la transacción se deshace, el evento tampoco existe; si se confirma, el relay del worker
lo publica en RabbitMQ aunque el broker esté caído en ese momento.
"""

from typing import Protocol

from app.domain.events.evento_dominio import EventoDominio


class Outbox(Protocol):
    async def agregar(self, evento: EventoDominio) -> None: ...
