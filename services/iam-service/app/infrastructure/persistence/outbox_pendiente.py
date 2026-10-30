"""Lado del relay de la tabla `outbox` (implementa OutboxPendiente), adaptado de catalog.

Usa su propia sesión y transacción, no la unidad de trabajo: el lote queda bloqueado
(`FOR UPDATE SKIP LOCKED`) mientras se publica, así dos relays nunca toman el mismo evento,
y el índice parcial `ix_outbox_pendientes` sirve a la búsqueda.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.estado_outbox import EstadoOutbox
from app.application.dto.evento_pendiente import EventoPendiente
from app.application.dto.resultado_lote import ResultadoLote
from app.infrastructure.persistence.models import Outbox

logger = logging.getLogger(__name__)

_PENDIENTE = Outbox.publicado_en.is_(None)


class SqlAlchemyOutboxPendiente:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def procesar_lote(
        self,
        limite: int,
        publicar: Callable[[EventoPendiente], Awaitable[None]],
        ahora: datetime,
    ) -> ResultadoLote:
        publicados: list[str] = []
        fallo = False
        async with self._session_factory() as session, session.begin():
            filas = await session.scalars(
                select(Outbox)
                .where(_PENDIENTE)
                .order_by(Outbox.creado_en, Outbox.event_id)
                .limit(limite)
                .with_for_update(skip_locked=True)
            )
            for fila in filas.all():
                evento = EventoPendiente(
                    event_id=fila.event_id,
                    event_type=fila.event_type,
                    sobre=fila.sobre,
                    creado_en=fila.creado_en,
                    intentos=fila.intentos,
                )
                try:
                    await publicar(evento)
                except Exception:
                    logger.warning(
                        "No se pudo publicar %s %s (intento %d)",
                        evento.event_type,
                        evento.event_id,
                        evento.intentos + 1,
                        exc_info=True,
                    )
                    fila.intentos += 1
                    fallo = True
                    break
                fila.publicado_en = ahora
                fila.intentos += 1
                publicados.append(evento.event_type)
        return ResultadoLote(publicados=tuple(publicados), fallo=fallo)

    async def estado(self) -> EstadoOutbox:
        async with self._session_factory() as session:
            pendientes, mas_antiguo = (
                await session.execute(
                    select(func.count(), func.min(Outbox.creado_en)).where(_PENDIENTE)
                )
            ).one()
        return EstadoOutbox(pendientes=pendientes, mas_antiguo=mas_antiguo)

    async def limpiar_publicados(self, antes_de: datetime) -> int:
        async with self._session_factory() as session, session.begin():
            resultado = await session.execute(
                delete(Outbox).where(
                    Outbox.publicado_en.is_not(None), Outbox.publicado_en < antes_de
                )
            )
        return resultado.rowcount or 0  # type: ignore[attr-defined]
