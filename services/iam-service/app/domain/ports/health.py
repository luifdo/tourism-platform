from typing import Protocol


class DatabaseProbe(Protocol):
    """Comprueba si la base de datos del servicio responde."""

    async def ping(self) -> bool: ...


class CacheProbe(Protocol):
    """Comprueba si la caché (Valkey: revocación de tokens) responde."""

    async def ping(self) -> bool: ...
