"""Puerto `RegistrosVencidos`: filas de control que ya no protegen nada y se pueden borrar."""

from datetime import datetime
from typing import Protocol


class RegistrosVencidos(Protocol):
    async def borrar_idempotencia_vencida(self) -> int:
        """Claves de `Idempotency-Key` vencidas; devuelve cuántas borró."""
        ...

    async def borrar_eventos_procesados(self, antes_de: datetime) -> int:
        """Registros de `evento_procesado` anteriores a `antes_de`; devuelve cuántos borró."""
        ...
