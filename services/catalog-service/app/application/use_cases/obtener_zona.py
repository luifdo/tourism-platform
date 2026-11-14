from uuid import UUID

from app.application.ports.consulta_zonas import ConsultaZonas
from app.domain.entities.zona import Zona
from app.domain.errors import NoEncontrado
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad


class ObtenerZona:
    """Detalle editable de una zona, activa o inactiva, con su polígono completo."""

    def __init__(self, consulta: ConsultaZonas) -> None:
        self._consulta = consulta

    async def execute(self, identidad: Identidad, zona_id: UUID) -> Zona:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        zona = await self._consulta.zona(zona_id)
        if zona is None:
            raise NoEncontrado(recurso="zona", id=str(zona_id))
        return zona
