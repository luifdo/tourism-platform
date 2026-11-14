from typing import Protocol
from uuid import UUID

from app.application.dto.zona_vista import ZonaVista
from app.domain.entities.zona import Zona


class ConsultaZonas(Protocol):
    async def activas(self) -> list[ZonaVista]: ...

    async def zona(self, zona_id: UUID) -> Zona | None:
        """Zona activa o inactiva, sin bloquear la fila (detalle editable de la Entidad)."""
        ...
