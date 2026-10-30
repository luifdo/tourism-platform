"""Puerto de persistencia `PrestadorRepository` (adaptador en persistence/repositorios)."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.prestador_perfil import PrestadorPerfil


class PrestadorRepository(Protocol):
    async def obtener(self, prestador_id: UUID) -> PrestadorPerfil | None: ...

    async def obtener_por_usuario(self, usuario_id: UUID) -> PrestadorPerfil | None: ...

    async def guardar(self, perfil: PrestadorPerfil) -> None: ...
