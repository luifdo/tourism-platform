"""Outbox en la tabla `outbox`: guarda el evento con su sobre común (envelope.v1.json).

El relay que lo publica en RabbitMQ y marca `publicado_en` llega con la mensajería.
"""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.events.evento_dominio import EventoDominio
from app.infrastructure.observabilidad.contexto_correlacion import correlation_id_actual
from app.infrastructure.persistence.modelos.outbox import OutboxModelo

PRODUCTOR = "catalog-service"


class SqlOutbox:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def agregar(self, evento: EventoDominio) -> None:
        event_id = uuid4()
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
            OutboxModelo(
                event_id=event_id,
                event_type=evento.tipo,
                sobre=sobre,
                creado_en=evento.ocurrido_en,
                intentos=0,
            )
        )
