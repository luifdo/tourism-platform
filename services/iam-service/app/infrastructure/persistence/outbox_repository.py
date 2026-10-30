"""Outbox en la tabla `outbox` (implementa Outbox): guarda el evento con su sobre común
(`contracts/events/envelope.v1.json`), en la sesión de la unidad de trabajo.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.events.evento_dominio import EventoDominio
from app.infrastructure.observabilidad.contexto_correlacion import correlation_id_actual
from app.infrastructure.persistence.models import Outbox

PRODUCTOR = "iam-service"


class SqlAlchemyOutbox:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def agregar(self, evento: EventoDominio) -> None:
        event_id = uuid.uuid4()
        sobre = {
            "event_id": str(event_id),
            "event_type": evento.tipo,
            "version": evento.version_esquema,
            "occurred_at": evento.ocurrido_en.isoformat(),
            "producer": PRODUCTOR,
            "payload": evento.payload(),  # se serializa ya: cambios posteriores no lo alteran
        }
        if correlation_id := correlation_id_actual():
            sobre["correlation_id"] = correlation_id
        self._session.add(
            Outbox(
                event_id=event_id,
                event_type=evento.tipo,
                sobre=sobre,
                creado_en=evento.ocurrido_en,
                intentos=0,
            )
        )
        await self._session.flush()
