from app.application.dto.pagina_servicios_editables import PaginaServiciosEditables
from app.application.ports.consulta_prestador import ConsultaPrestador
from app.application.use_cases.acceso_prestador import exigir_perfil
from app.domain.errors import DatoInvalido
from app.domain.value_objects.identidad import Identidad, Rol


class ListarServiciosPrestador:
    """UC18: el panel del prestador, con inactivos y textos en ambos idiomas.

    Un perfil suspendido puede ver sus servicios (sin editarlos).
    """

    def __init__(self, consulta: ConsultaPrestador) -> None:
        self._consulta = consulta

    async def execute(
        self, identidad: Identidad, pagina: int, tamano: int
    ) -> PaginaServiciosEditables:
        identidad.exigir_rol(Rol.PRESTADOR)
        if pagina < 1:
            raise DatoInvalido(campo="pagina", regla="minimo", minimo=1)
        if not 1 <= tamano <= 100:
            raise DatoInvalido(campo="tamano", regla="rango", minimo=1, maximo=100)
        perfil = exigir_perfil(await self._consulta.perfil_de_usuario(identidad.usuario_id))
        return await self._consulta.servicios(perfil.id, pagina, tamano)
