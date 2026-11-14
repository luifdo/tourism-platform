import uuid
from collections.abc import Callable
from datetime import datetime

from app.application.use_cases.consultar_verificacion import Verificacion
from app.domain.entities.documento_verificacion import (
    DocumentoVerificacion,
    estado_verificacion,
)
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import (
    CuentaSuprimidaError,
    NoEsPrestadorError,
    UsuarioNoEncontradoError,
)
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import Rol


class RevisionPrestador:
    """Pasos comunes de UC28 (aprobar o rechazar a un prestador).

    La cuenta se bloquea (`FOR UPDATE`) durante la revisión: una carga simultánea del
    prestador (que también la bloquea) espera, y nunca se revisa un documento que ya fue
    reemplazado.
    """

    def __init__(self, uow: UnitOfWork, reloj: Callable[[], datetime]) -> None:
        self._uow = uow
        self._reloj = reloj

    @staticmethod
    async def _prestador_bloqueado(uow: UnitOfWork, usuario_id: uuid.UUID) -> Usuario:
        prestador = await uow.usuarios.find_by_id_para_actualizar(usuario_id)
        if prestador is None:
            raise UsuarioNoEncontradoError()
        if prestador.suprimido:
            raise CuentaSuprimidaError()
        if prestador.rol is not Rol.PRESTADOR:
            raise NoEsPrestadorError()
        return prestador


def verificacion(prestador: Usuario, vigentes: list[DocumentoVerificacion]) -> Verificacion:
    assert prestador.id is not None
    return Verificacion(
        usuario_id=prestador.id,
        razon_social=prestador.razon_social,
        estado=estado_verificacion(vigentes),
        documentos=vigentes,
    )
