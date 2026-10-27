from app.application.dto.criterios_busqueda import CriteriosBusqueda
from app.application.dto.pagina_servicios import PaginaServicios
from app.application.ports.consulta_servicios import ConsultaServicios


class BuscarServicios:
    """UC7 y UC8: listar y buscar servicios activos con filtros combinados.

    La caché de 300 s es transparente: la aporta el adaptador que se inyecta como consulta.
    """

    def __init__(self, consulta: ConsultaServicios) -> None:
        self._consulta = consulta

    async def execute(self, criterios: CriteriosBusqueda) -> PaginaServicios:
        return await self._consulta.buscar(criterios)
