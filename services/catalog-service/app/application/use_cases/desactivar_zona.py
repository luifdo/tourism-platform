from uuid import UUID

from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.application.use_cases.escritura_zona import EscrituraZona
from app.domain.entities.zona import Zona
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad


class DesactivarZona:
    """La zona deja de ofrecerse en filtros y mapas; el histórico de demanda se conserva.

    Sus servicios pasan a otra zona activa que los cubra, o quedan sin zona. Con alertas
    vigentes no se puede (ZONA_EN_USO). Repetir la operación no cambia nada ni se audita.
    """

    def __init__(
        self, unidad_de_trabajo: FabricaUnidadDeTrabajo, escritura: EscrituraZona, reloj: Reloj
    ) -> None:
        self._uow = unidad_de_trabajo
        self._escritura = escritura
        self._reloj = reloj

    async def execute(self, identidad: Identidad, zona_id: UUID, version_esperada: int) -> Zona:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        ahora = self._reloj.ahora()
        async with self._uow() as uow:
            zona = await uow.zonas.obtener(zona_id)
            if zona is None:
                raise NoEncontrado(recurso="zona", id=str(zona_id))
            alertas = await uow.alertas.contar_vigentes_de_zona(zona.id, ahora)
            if not zona.desactivar(version_esperada, alertas):
                return zona
            await self._escritura.guardar_y_auditar(
                uow, zona, identidad, "ZONA_DESACTIVADA", ahora, reasignar=True
            )
            await uow.confirmar()
        await self._escritura.despues_de_confirmar()
        return zona
