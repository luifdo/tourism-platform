import uuid

from app.domain.entities.usuario import Usuario
from app.domain.exceptions import UsuarioNoEncontradoError
from app.domain.ports.unit_of_work import UnitOfWork


class ObtenerPerfil:
    """UC4: los datos de la cuenta del propio usuario."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, usuario_id: uuid.UUID) -> Usuario:
        async with self._uow as uow:
            usuario = await uow.usuarios.find_by_id(usuario_id)
        if usuario is None or usuario.suprimido:
            raise UsuarioNoEncontradoError()
        return usuario
