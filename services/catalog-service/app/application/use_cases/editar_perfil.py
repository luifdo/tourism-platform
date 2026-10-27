from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo, exigir_perfil
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.texto_traducido import TextoTraducido


class EditarPerfil:
    """Teléfono, dirección y política de cancelación (UC4). La razón social viene de iam.

    No invalida la caché: esos datos solo salen en la ficha del servicio, que no se cachea.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo) -> None:
        self._uow = unidad_de_trabajo

    async def execute(
        self,
        identidad: Identidad,
        version_esperada: int,
        telefono: str | None,
        direccion: str | None,
        politica_cancelacion: TextoTraducido | None,
    ) -> PrestadorPerfil:
        identidad.exigir_rol(Rol.PRESTADOR)
        async with self._uow() as uow:
            perfil = exigir_perfil(await uow.prestadores.obtener_por_usuario(identidad.usuario_id))
            perfil.editar(version_esperada, telefono, direccion, politica_cancelacion)
            await uow.prestadores.guardar(perfil)
            await uow.confirmar()
        return perfil
