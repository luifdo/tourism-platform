from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.filtro_usuarios import FiltroUsuarios, PaginaUsuarios


class ListarUsuarios:
    """UC27: listado de usuarios para el Admin, con filtros y paginación."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, filtro: FiltroUsuarios) -> PaginaUsuarios:
        async with self._uow as uow:
            return await uow.usuarios.listar(filtro)
