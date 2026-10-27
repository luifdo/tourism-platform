from enum import StrEnum
from uuid import UUID

from app.application.dto.servicio_editable import ServicioEditable
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo, exigir_perfil
from app.application.use_cases.escritura_servicio import EscrituraServicio
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.identidad import Identidad, Rol


class EstadoServicio(StrEnum):
    ACTIVO = "activo"
    INACTIVO = "inactivo"


class CambiarEstadoServicio:
    """UC18: desactivar o reactivar una oferta. No se borra; deja de mostrarse.

    Si ya estaba en ese estado no cambia la versión ni se publica nada, así repetir la
    operación (por ejemplo, un reenvío de la PWA) no genera eventos de más.
    """

    def __init__(
        self, unidad_de_trabajo: FabricaUnidadDeTrabajo, escritura: EscrituraServicio, reloj: Reloj
    ) -> None:
        self._uow = unidad_de_trabajo
        self._escritura = escritura
        self._reloj = reloj

    async def execute(
        self,
        identidad: Identidad,
        servicio_id: UUID,
        version_esperada: int,
        estado: EstadoServicio,
    ) -> ServicioEditable:
        identidad.exigir_rol(Rol.PRESTADOR)
        ahora = self._reloj.ahora()
        async with self._uow() as uow:
            perfil = exigir_perfil(await uow.prestadores.obtener_por_usuario(identidad.usuario_id))
            servicio = await uow.servicios.obtener(servicio_id)
            if servicio is None:
                raise NoEncontrado(recurso="servicio", id=str(servicio_id))
            if estado is EstadoServicio.ACTIVO:
                cambio = servicio.reactivar(perfil, version_esperada, ahora)
            else:
                cambio = servicio.desactivar(perfil, version_esperada, ahora)
            if not cambio:
                return await self._escritura.leer(servicio)
            await self._escritura.guardar_y_publicar(uow, servicio, ahora)
            await uow.confirmar()
        return await self._escritura.despues_de_confirmar(servicio)
