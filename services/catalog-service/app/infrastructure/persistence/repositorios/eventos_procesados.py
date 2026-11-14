"""Registro de eventos ya procesados por cada consumidor (tabla `evento_procesado`)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.modelos.evento_procesado import EventoProcesadoModelo


class SqlEventosProcesados:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def registrar(self, event_id: UUID, consumidor: str) -> bool:
        resultado = await self._session.execute(
            insert(EventoProcesadoModelo)
            .values(event_id=event_id, consumidor=consumidor)
            .on_conflict_do_nothing()
            .returning(EventoProcesadoModelo.event_id)
        )
        return resultado.first() is not None

    async def ya_procesado(self, event_id: UUID, consumidor: str) -> bool:
        m = EventoProcesadoModelo
        return (
            await self._session.scalar(
                select(m.event_id).where(m.event_id == event_id, m.consumidor == consumidor)
            )
            is not None
        )
