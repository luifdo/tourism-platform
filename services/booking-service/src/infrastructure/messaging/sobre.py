"""Sobre común de los eventos (contracts/events/envelope.v1.json)."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from domain.eventos import EventoDominio

PRODUCTOR = "booking-service"


def armar_sobre(evento: EventoDominio, correlation_id: str | None) -> dict[str, Any]:
    sobre: dict[str, Any] = {
        "event_id": str(uuid4()),
        "event_type": evento.tipo,
        "version": 1,
        "occurred_at": datetime.now(UTC).isoformat(),
        "producer": PRODUCTOR,
        "payload": evento.payload,
    }
    if correlation_id:
        sobre["correlation_id"] = correlation_id
    return sobre
