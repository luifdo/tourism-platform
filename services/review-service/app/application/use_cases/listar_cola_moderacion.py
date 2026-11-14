from app.application.dto.pagina_moderacion import PaginaModeracion
from app.application.ports.consulta_resenas import ConsultaResenas
from app.domain.value_objects.estado_resena import EstadoResena
from app.domain.value_objects.identidad import Identidad, Rol


class ListarColaModeracion:
    """UC29: la cola del Administrador, con el autor (para auditar) y los reportes abiertos."""

    def __init__(self, consulta: ConsultaResenas) -> None:
        self._consulta = consulta

    async def execute(
        self, identidad: Identidad, estado: EstadoResena | None, pagina: int, tamano: int
    ) -> PaginaModeracion:
        identidad.exigir_rol(Rol.ADMIN)
        return await self._consulta.cola_moderacion(estado, pagina, tamano)
