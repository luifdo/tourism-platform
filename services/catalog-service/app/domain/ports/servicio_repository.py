"""Puerto de persistencia `ServicioRepository` (adaptador en persistence/repositorios)."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.atractivo_servicio import AtractivoServicio


class ServicioRepository(Protocol):
    async def obtener(self, servicio_id: UUID) -> AtractivoServicio | None: ...

    async def listar_por_prestador(self, prestador_id: UUID) -> list[AtractivoServicio]: ...

    async def guardar(self, servicio: AtractivoServicio) -> None: ...
