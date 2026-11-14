from uuid import UUID

from app.application.ports.consulta_resenas import ConsultaResenas
from app.domain.entities.resena import Resena
from app.domain.errors import NoEncontrado


class ObtenerResenaPublica:
    """Ruta pública: una reseña visible; en revisión u oculta responde como si no existiera."""

    def __init__(self, consulta: ConsultaResenas) -> None:
        self._consulta = consulta

    async def execute(self, resena_id: UUID) -> Resena:
        resena = await self._consulta.publica(resena_id)
        if resena is None:
            raise NoEncontrado(resena=str(resena_id))
        return resena
