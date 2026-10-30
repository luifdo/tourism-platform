import uuid
from dataclasses import dataclass

from app.domain.entities.documento_verificacion import (
    DocumentoVerificacion,
    EstadoVerificacion,
    estado_verificacion,
)
from app.domain.exceptions import NoEsPrestadorError, UsuarioNoEncontradoError
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import Rol


@dataclass(frozen=True)
class Verificacion:
    usuario_id: uuid.UUID
    razon_social: str | None
    estado: EstadoVerificacion
    documentos: list[DocumentoVerificacion]


class ConsultarVerificacion:
    """Estado de verificación de un prestador y sus documentos.

    El prestador ve sus vigentes (UC37); el Admin, el historial completo (UC28).
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, usuario_id: uuid.UUID, historial: bool = False) -> Verificacion:
        async with self._uow as uow:
            usuario = await uow.usuarios.find_by_id(usuario_id)
            if usuario is None:
                raise UsuarioNoEncontradoError()
            if usuario.rol is not Rol.PRESTADOR:
                raise NoEsPrestadorError()
            vigentes = await uow.documentos.vigentes(usuario_id)
            documentos = await uow.documentos.historial(usuario_id) if historial else vigentes
        return Verificacion(
            usuario_id=usuario_id,
            razon_social=usuario.razon_social,
            estado=estado_verificacion(vigentes),
            documentos=documentos,
        )
