from typing import Protocol


class DatabaseProbe(Protocol):
    """Comprueba si la base de datos del servicio responde."""

    async def ping(self) -> bool: ...
