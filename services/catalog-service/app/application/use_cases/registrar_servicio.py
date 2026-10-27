from app.application.dto.servicio_editable import ServicioEditable
from app.application.ports.almacen_imagenes import AlmacenImagenes
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo, exigir_perfil
from app.application.use_cases.escritura_servicio import EscrituraServicio
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.identidad import Identidad, Rol


class RegistrarServicio:
    """UC17: un prestador con perfil activo registra una oferta georreferenciada."""

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

    async def execute(self, identidad: Identidad, datos: DatosServicio) -> ServicioEditable:
        identidad.exigir_rol(Rol.PRESTADOR)
        ahora = self._reloj.ahora()
        async with self._uow() as uow:
            perfil = exigir_perfil(await uow.prestadores.obtener_por_usuario(identidad.usuario_id))
            servicio = AtractivoServicio.registrar(
                perfil, datos, self._imagenes.origen_de(perfil.id), ahora
            )
            await self._escritura.guardar_y_publicar(uow, servicio, ahora)
            await uow.confirmar()
        return await self._escritura.despues_de_confirmar(servicio)
