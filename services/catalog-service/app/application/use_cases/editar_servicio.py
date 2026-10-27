from uuid import UUID

from app.application.dto.servicio_editable import ServicioEditable
from app.application.ports.almacen_imagenes import AlmacenImagenes
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo, exigir_perfil
from app.application.use_cases.escritura_servicio import EscrituraServicio
from app.domain.entities.atractivo_servicio import DatosServicio
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.identidad import Identidad, Rol


class EditarServicio:
    """UC18: el dueño edita su oferta con la versión que leyó (`If-Match`)."""

    def __init__(
        self,
        unidad_de_trabajo: FabricaUnidadDeTrabajo,
        escritura: EscrituraServicio,
        imagenes: AlmacenImagenes,
        reloj: Reloj,
    ) -> None:
        self._uow = unidad_de_trabajo
        self._escritura = escritura
        self._imagenes = imagenes
        self._reloj = reloj

    async def execute(
        self,
        identidad: Identidad,
        servicio_id: UUID,
        version_esperada: int,
        datos: DatosServicio,
    ) -> ServicioEditable:
        identidad.exigir_rol(Rol.PRESTADOR)
        ahora = self._reloj.ahora()
        async with self._uow() as uow:
            # Siempre perfil y luego servicio: el mismo orden de bloqueo en toda escritura.
            perfil = exigir_perfil(await uow.prestadores.obtener_por_usuario(identidad.usuario_id))
            servicio = await uow.servicios.obtener(servicio_id)
            if servicio is None:
                raise NoEncontrado(recurso="servicio", id=str(servicio_id))
            servicio.editar(
                perfil, version_esperada, datos, self._imagenes.origen_de(perfil.id), ahora
            )
            await self._escritura.guardar_y_publicar(uow, servicio, ahora)
            await uow.confirmar()
        return await self._escritura.despues_de_confirmar(servicio)
