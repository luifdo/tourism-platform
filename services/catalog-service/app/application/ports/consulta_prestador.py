"""Puerto de lectura del panel del prestador: lee sin bloquear filas (a diferencia de la UoW)."""

from typing import Protocol
from uuid import UUID

from app.application.dto.pagina_servicios_editables import PaginaServiciosEditables
from app.application.dto.servicio_editable import ServicioEditable
from app.domain.entities.prestador_perfil import PrestadorPerfil


class ConsultaPrestador(Protocol):
    async def perfil_de_usuario(self, usuario_id: UUID) -> PrestadorPerfil | None: ...

    async def servicios(
        self, prestador_id: UUID, pagina: int, tamano: int
    ) -> PaginaServiciosEditables:
        """Todos sus servicios, activos e inactivos, del más reciente al más antiguo."""
        ...

    async def servicio(self, servicio_id: UUID) -> ServicioEditable | None: ...
