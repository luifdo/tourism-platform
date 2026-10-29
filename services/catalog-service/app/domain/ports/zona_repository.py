"""Puerto de persistencia `ZonaRepository` (adaptador en persistence/repositorios)."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.zona import Zona
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.geo import Coordenada


class ZonaRepository(Protocol):
    async def obtener(self, zona_id: UUID) -> Zona | None: ...

    async def obtener_por_codigo(self, codigo: CodigoZona) -> Zona | None: ...

    async def zona_de(self, punto: Coordenada) -> UUID | None:
        """Zona activa que contiene el punto (`ST_Covers`), o None."""
        ...

    async def reasignar_servicios(self, zona_id: UUID) -> None:
        """Recalcula la zona de los servicios afectados cuando cambia el polígono."""
        ...

    async def guardar(self, zona: Zona) -> None: ...
