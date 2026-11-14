"""Puerto de persistencia `EventosProcesados` (adaptador en persistence/repositorios)."""

from typing import Protocol
from uuid import UUID


class EventosProcesados(Protocol):
    async def registrar(self, event_id: UUID, consumidor: str) -> bool:
        """Registra el evento en la misma transacción que su efecto.

        Devuelve False si ya estaba registrado (duplicado: se reconoce y se descarta).
        """
        ...

    async def ya_procesado(self, event_id: UUID, consumidor: str) -> bool:
        """Para efectos que no son transaccionales (un correo): se consulta antes de enviar y
        se registra después, así una caída entre ambos reenvía en lugar de perder."""
        ...
