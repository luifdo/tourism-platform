from uuid import UUID

from app.application.dto.orden_resenas import OrdenResenas
from app.application.dto.pagina_resenas import PaginaResenas
from app.application.ports.consulta_resenas import ConsultaResenas


class ListarResenasServicio:
    """Ruta pública: las reseñas visibles de un servicio. La usa la tool `resenas_servicio`
    del Módulo 5; las que están en revisión u ocultas no aparecen."""

    def __init__(self, consulta: ConsultaResenas) -> None:
        self._consulta = consulta

    async def execute(
        self, servicio_id: UUID, orden: OrdenResenas, pagina: int, tamano: int
    ) -> PaginaResenas:
        return await self._consulta.de_servicio(servicio_id, orden, pagina, tamano)
