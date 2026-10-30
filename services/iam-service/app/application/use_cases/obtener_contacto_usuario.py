import uuid

from app.domain.entities.usuario import Usuario
from app.domain.exceptions import UsuarioNoEncontradoError
from app.domain.ports.unit_of_work import UnitOfWork


class ObtenerContactoUsuario:
    """Contacto de un usuario para los correos de catalog (C-15, `iam-interno.yaml`).

    Un usuario inactivo también se devuelve: debe seguir recibiendo los avisos de sus
    reservas (por ejemplo, la cancelación). Los datos suprimidos serán 404 (bloque 6, C-27).
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, usuario_id: uuid.UUID) -> Usuario:
        async with self._uow as uow:
            usuario = await uow.usuarios.find_by_id(usuario_id)
        if usuario is None:
            raise UsuarioNoEncontradoError()
        return usuario
