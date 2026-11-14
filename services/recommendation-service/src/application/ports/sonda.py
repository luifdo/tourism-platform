from typing import Protocol


class Sonda(Protocol):
    """Comprueba si una dependencia propia del servicio (PostgreSQL, Valkey) responde."""

    async def ping(self) -> bool: ...
