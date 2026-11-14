"""Puerto de persistencia `ReporteRepository` (adaptador en persistence/repositorios)."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.entities.reporte_resena import ReporteResena


class ReporteRepository(Protocol):
    async def agregar(self, reporte: ReporteResena) -> None:
        """Lanza `YaReportada` si el usuario ya reportó esa reseña."""
        ...

    async def recientes_de_usuario(self, usuario_id: UUID, desde: datetime) -> list[datetime]:
        """Cuándo reportó el usuario desde `desde`. Ordena los reportes simultáneos del
        mismo usuario hasta el final de la transacción, para que el límite sea exacto."""
        ...

    async def resolver_abiertos(self, resena_id: UUID, ahora: datetime) -> int:
        """Cierra los reportes sin resolver de la reseña; devuelve cuántos."""
        ...
