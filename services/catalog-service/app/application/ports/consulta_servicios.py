"""Puerto de lectura del catálogo.

Está en la capa de aplicación (no en domain/ports) porque devuelve DTO de lectura, no
entidades. No bloquea filas: las lecturas públicas nunca esperan a una edición.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.dto.criterios_busqueda import CriteriosBusqueda
from app.application.dto.nombre_servicio import NombreServicio
from app.application.dto.pagina_servicios import PaginaServicios
from app.application.dto.servicio_detalle import ServicioDetalle


class ConsultaServicios(Protocol):
    async def buscar(self, criterios: CriteriosBusqueda) -> PaginaServicios: ...

    async def detalle(self, servicio_id: UUID, ahora: datetime) -> ServicioDetalle | None:
        """Solo servicios activos; None si no existe o está inactivo. `ahora` filtra alertas."""
        ...

    async def nombres(self, ids: Sequence[UUID]) -> list[NombreServicio]:
        """Activos o no; los ids que no existen no aparecen. Sin orden garantizado."""
        ...
