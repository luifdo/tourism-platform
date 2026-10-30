from uuid import UUID

from app.application.dto.pagina_resenas import PaginaResenas
from app.application.ports.consulta_resenas import ConsultaResenas
from app.domain.errors import NoEsDueno
from app.domain.value_objects.identidad import Identidad, Rol


class ListarResenasPrestador:
    """El prestador ve las reseñas de sus servicios, publicadas y en revisión (sabe cuáles
    están en revisión), con su versión para responder. Siguen siendo anónimas."""

    def __init__(self, consulta: ConsultaResenas) -> None:
        self._consulta = consulta

    async def execute(
        self,
        identidad: Identidad,
        servicio_id: UUID | None,
        sin_respuesta: bool,
        pagina: int,
        tamano: int,
    ) -> PaginaResenas:
        identidad.exigir_rol(Rol.PRESTADOR)
        if servicio_id is not None and (
            await self._consulta.dueno_de(servicio_id) != identidad.usuario_id
        ):
            raise NoEsDueno(servicio=str(servicio_id))
        return await self._consulta.del_prestador(
            identidad.usuario_id, servicio_id, sin_respuesta, pagina, tamano
        )
