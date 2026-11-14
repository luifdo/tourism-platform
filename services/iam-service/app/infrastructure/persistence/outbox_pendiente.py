"""Lado del relay de la tabla `outbox` (implementa OutboxPendiente), adaptado de catalog.

Usa su propia sesión y transacción, no la unidad de trabajo: el lote queda bloqueado
(`FOR UPDATE SKIP LOCKED`) mientras se publica, así dos relays nunca toman el mismo evento,
y el índice parcial `ix_outbox_pendientes` sirve a la búsqueda.

Los tipos retenidos (C-63) se excluyen en el WHERE: nunca ocupan el lote ni bloquean a los
demás, y quedan pendientes, sin `publicado_en`, hasta que se liberen.
"""

import logging
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime

from sqlalchemy import ColumnElement, Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.estado_outbox import EstadoOutbox
from app.application.dto.evento_pendiente import EventoPendiente
from app.application.dto.resultado_lote import ResultadoLote
from app.infrastructure.persistence.models import Outbox

logger = logging.getLogger(__name__)

_PENDIENTE = Outbox.publicado_en.is_(None)


class SqlAlchemyOutboxPendiente:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], retenidos: Iterable[str] = ()
    ) -> None:
        self._session_factory = session_factory
        self._retenidos = tuple(dict.fromkeys(retenidos))

    def _publicables(self) -> list[ColumnElement[bool]]:
        condiciones = [_PENDIENTE]
        # Sin lista no se agrega nada: un NOT IN vacío no aporta y confunde al planificador.
        if self._retenidos:
            condiciones.append(Outbox.event_type.not_in(self._retenidos))
        return condiciones

    def consulta_lote(self, limite: int) -> Select[tuple[Outbox]]:
        """La búsqueda del lote. Pública para comprobar con EXPLAIN que usa el índice."""
        return (
            select(Outbox)
            .where(*self._publicables())
            .order_by(Outbox.creado_en, Outbox.event_id)
            .limit(limite)
            .with_for_update(skip_locked=True)
        )

    async def procesar_lote(
        self,
        limite: int,
        publicar: Callable[[EventoPendiente], Awaitable[None]],
        ahora: datetime,
    ) -> ResultadoLote:
        publicados: list[str] = []
        fallo = False
        async with self._session_factory() as session, session.begin():
            filas = await session.scalars(self.consulta_lote(limite))
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
        retenidos = dict.fromkeys(self._retenidos, 0)
        async with self._session_factory() as session:
            pendientes, mas_antiguo = (
                await session.execute(
                    select(func.count(), func.min(Outbox.creado_en)).where(*self._publicables())
                )
            ).one()
            if self._retenidos:
                por_tipo = await session.execute(
                    select(Outbox.event_type, func.count())
                    .where(_PENDIENTE, Outbox.event_type.in_(self._retenidos))
                    .group_by(Outbox.event_type)
                )
                retenidos.update({tipo: n for tipo, n in por_tipo})
        return EstadoOutbox(pendientes=pendientes, mas_antiguo=mas_antiguo, retenidos=retenidos)

    async def limpiar_publicados(self, antes_de: datetime) -> int:
        async with self._session_factory() as session, session.begin():
            resultado = await session.execute(
                delete(Outbox).where(
                    Outbox.publicado_en.is_not(None), Outbox.publicado_en < antes_de
                )
            )
        return resultado.rowcount or 0  # type: ignore[attr-defined]
