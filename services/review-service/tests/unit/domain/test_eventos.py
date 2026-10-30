"""Los eventos que arma el dominio cumplen su esquema en contracts/events/."""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from app.domain.events.evento_dominio import EventoDominio
from app.domain.value_objects.decision_moderacion import DecisionModeracion
from tests.unit.domain.comun import ADMIN, AHORA, resena


def sobre(evento: EventoDominio) -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": evento.tipo,
        "version": evento.version_esquema,
        "occurred_at": evento.ocurrido_en.isoformat(),
        "producer": "review-service",
        "correlation_id": str(uuid4()),
        "payload": evento.payload(),
    }


def test_publicada_y_ocultada_cumplen_el_contrato(
    validar_evento: Callable[[dict[str, Any]], None],
) -> None:
    r = resena()
    ocultada = r.moderar(ADMIN, 1, DecisionModeracion.OCULTAR, "Spam", AHORA)
    publicada = r.moderar(ADMIN, 2, DecisionModeracion.PUBLICAR, None, AHORA)
    assert ocultada is not None and publicada is not None
    for evento in (ocultada, publicada):
        validar_evento(sobre(evento))
