from typing import Protocol


class InvalidadorCache(Protocol):
    async def invalidar(self) -> None:
        """Se llama después de confirmar un cambio del catálogo. Nunca falla."""
        ...
