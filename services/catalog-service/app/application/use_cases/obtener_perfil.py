from app.application.ports.consulta_prestador import ConsultaPrestador
from app.application.use_cases.acceso_prestador import exigir_perfil
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.identidad import Identidad, Rol


class ObtenerPerfil:
    """Perfil comercial del prestador autenticado.

    Un perfil suspendido se puede ver (con `activo=false`) pero no editar.
    """

    def __init__(self, consulta: ConsultaPrestador) -> None:
        self._consulta = consulta

    async def execute(self, identidad: Identidad) -> PrestadorPerfil:
        identidad.exigir_rol(Rol.PRESTADOR)
        return exigir_perfil(await self._consulta.perfil_de_usuario(identidad.usuario_id))
