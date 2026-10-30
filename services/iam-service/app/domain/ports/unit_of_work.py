from types import TracebackType
from typing import Protocol, Self

from app.domain.ports.auditoria_repository import AuditoriaRepository
from app.domain.ports.documento_repository import DocumentoRepository
from app.domain.ports.outbox import Outbox
from app.domain.ports.usuario_repository import UsuarioRepository


class UnitOfWork(Protocol):
    """Transacción que agrupa los repositorios. Al salir del bloque sin commit(), hace rollback."""

    usuarios: UsuarioRepository
    auditoria: AuditoriaRepository
    documentos: DocumentoRepository
    outbox: Outbox

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
