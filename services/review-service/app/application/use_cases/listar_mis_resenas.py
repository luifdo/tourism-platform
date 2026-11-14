from app.application.dto.pagina_resenas import PaginaResenas
from app.application.ports.consulta_resenas import ConsultaResenas
from app.domain.value_objects.identidad import Identidad, Rol


class ListarMisResenas:
    """El turista ve todas sus reseñas, también las que están en revisión u ocultas."""

    def __init__(self, consulta: ConsultaResenas) -> None:
        self._consulta = consulta

    async def execute(self, identidad: Identidad, pagina: int, tamano: int) -> PaginaResenas:
        identidad.exigir_rol(Rol.TURISTA)
        return await self._consulta.del_turista(identidad.usuario_id, pagina, tamano)
