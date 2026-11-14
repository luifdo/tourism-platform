from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.filtro_prestadores import FiltroPrestadores, PaginaPrestadores


class ListarPrestadores:
    """UC28: cola de revisión del Admin (prestadores por estado de verificación)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, filtro: FiltroPrestadores) -> PaginaPrestadores:
        async with self._uow as uow:
            return await uow.documentos.listar_prestadores(filtro)
