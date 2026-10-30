from typing import Protocol

from app.application.dto.evento_pendiente import EventoPendiente


class PublicadorEventos(Protocol):
    async def publicar(self, evento: EventoPendiente) -> None:
        """Vuelve solo cuando el broker confirmó el mensaje; si no, lanza una excepción."""
        ...
