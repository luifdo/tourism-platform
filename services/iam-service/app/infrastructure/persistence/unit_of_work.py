from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.persistence.auditoria_repository import SqlAlchemyAuditoriaRepository
from app.infrastructure.persistence.documento_repository import SqlAlchemyDocumentoRepository
from app.infrastructure.persistence.outbox_repository import SqlAlchemyOutbox
from app.infrastructure.persistence.usuario_repository import SqlAlchemyUsuarioRepository


class SqlAlchemyUnitOfWork:
    """Implementa UnitOfWork: una AsyncSession (una transacción) compartida por los repositorios."""

    usuarios: SqlAlchemyUsuarioRepository
    auditoria: SqlAlchemyAuditoriaRepository
    documentos: SqlAlchemyDocumentoRepository
    outbox: SqlAlchemyOutbox

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.usuarios = SqlAlchemyUsuarioRepository(self._session)
        self.auditoria = SqlAlchemyAuditoriaRepository(self._session)
        self.documentos = SqlAlchemyDocumentoRepository(self._session)
        self.outbox = SqlAlchemyOutbox(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            # Tras un commit() no queda nada pendiente y esto no hace nada.
            await self.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        assert self._session is not None
        await self._session.commit()

    async def rollback(self) -> None:
        assert self._session is not None
        await self._session.rollback()
