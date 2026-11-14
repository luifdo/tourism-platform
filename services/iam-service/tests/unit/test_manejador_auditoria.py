"""Traducción de `auditoria.registrada.v1` a la bitácora y validación del contrato."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.registrar_evento_auditoria import RegistrarEventoAuditoria
from app.domain.value_objects.enums import ResultadoAuditoria
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.evento_invalido import EventoInvalido
from app.infrastructure.messaging.manejador_auditoria import ManejadorAuditoria
from tests.fakes import FakeUnitOfWork

OCURRIO = datetime(2026, 10, 29, 14, 0, tzinfo=UTC)


def sobre(payload: dict[str, Any] | None = None, **cambios: Any) -> SobreEvento:
    datos = {
        "event_id": str(uuid.uuid4()),
        "event_type": "auditoria.registrada",
        "version": 1,
        "occurred_at": OCURRIO.isoformat(),
        "producer": "booking-service",
        "correlation_id": "corr-booking-7",
        "payload": {"accion": "RESERVA_CANCELADA", "resultado": "EXITO"}
        if payload is None
        else payload,
    }
    return SobreEvento.model_validate(datos | cambios)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def manejador(uow: FakeUnitOfWork) -> ManejadorAuditoria:
    return ManejadorAuditoria(RegistrarEventoAuditoria(lambda: uow))


async def test_traduce_el_sobre_y_el_payload(
    manejador: ManejadorAuditoria, uow: FakeUnitOfWork
) -> None:
    usuario_id = uuid.uuid4()
    recibido = sobre(
        {
            "usuario_id": str(usuario_id),
            "accion": "ACCESS_DENIED",
            "resultado": "DENEGADO",
            "ip_origen": "181.49.10.7",
            "detalles": {"ruta": "/api/booking/reservas", "metodo": "POST"},
        }
    )

    assert await manejador(recibido) is ResultadoConsumo.APLICADO

    guardado = uow.auditoria.eventos[recibido.event_id]
    assert guardado.servicio_origen == "booking-service"
    assert guardado.ocurrido_en == OCURRIO
    assert guardado.accion == "ACCESS_DENIED"
    assert guardado.resultado is ResultadoAuditoria.DENEGADO
    assert guardado.usuario_id == usuario_id
    assert guardado.ip_origen == "181.49.10.7"
    assert guardado.detalles == {"ruta": "/api/booking/reservas", "metodo": "POST"}
    assert guardado.correlation_id == "corr-booking-7"


@pytest.mark.parametrize(
    ("del_contrato", "en_la_base"),
    [
        ("EXITO", ResultadoAuditoria.EXITO),
        ("DENEGADO", ResultadoAuditoria.DENEGADO),
        ("ERROR", ResultadoAuditoria.ERROR),
    ],
)
async def test_resultado_del_contrato_a_los_valores_del_srs(
    manejador: ManejadorAuditoria, uow: FakeUnitOfWork, del_contrato: str, en_la_base: Any
) -> None:
    recibido = sobre({"accion": "EXPORT", "resultado": del_contrato})

    await manejador(recibido)

    assert uow.auditoria.eventos[recibido.event_id].resultado is en_la_base


async def test_lo_opcional_ausente_y_usuario_nulo(
    manejador: ManejadorAuditoria, uow: FakeUnitOfWork
) -> None:
    recibido = sobre({"usuario_id": None, "accion": "RESERVA_EXPIRADA", "resultado": "EXITO"})
    sin_correlacion = sobre(correlation_id=None)

    await manejador(recibido)
    await manejador(sin_correlacion)

    guardado = uow.auditoria.eventos[recibido.event_id]
    assert (guardado.usuario_id, guardado.ip_origen, guardado.detalles) == (None, None, {})
    assert uow.auditoria.eventos[sin_correlacion.event_id].correlation_id is None


async def test_duplicado(manejador: ManejadorAuditoria) -> None:
    recibido = sobre()
    await manejador(recibido)

    assert await manejador(recibido) is ResultadoConsumo.DUPLICADO


@pytest.mark.parametrize(
    "payload",
    [
        {"resultado": "EXITO"},  # falta accion
        {"accion": "EXPORT"},  # falta resultado
        {"accion": "EXPORT", "resultado": "Exito"},  # valor del SRS, no del contrato
        {"accion": "EXPORT", "resultado": "EXITO", "extra": 1},  # additionalProperties: false
        {"accion": "", "resultado": "EXITO"},
        {"accion": "A" * 51, "resultado": "EXITO"},  # no cabe en la columna
        {"accion": "EXPORT", "resultado": "EXITO", "usuario_id": "no-uuid"},
        {"accion": "EXPORT", "resultado": "EXITO", "ip_origen": None},  # es string, no nulo
        {"accion": "EXPORT", "resultado": "EXITO", "ip_origen": 10},
        {"accion": "EXPORT", "resultado": "EXITO", "detalles": ["no", "objeto"]},
    ],
)
async def test_payload_fuera_del_contrato(
    manejador: ManejadorAuditoria, uow: FakeUnitOfWork, payload: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        await manejador(sobre(payload))
    assert uow.auditoria.eventos == {}


async def test_otro_tipo_de_evento_es_invalido(manejador: ManejadorAuditoria) -> None:
    with pytest.raises(EventoInvalido):
        await manejador(sobre(event_type="reserva.confirmada"))


async def test_producer_que_no_cabe_en_servicio_origen(manejador: ManejadorAuditoria) -> None:
    with pytest.raises(EventoInvalido):
        await manejador(sobre(producer="x" * 51))


def test_occurred_at_sin_zona_horaria_no_cumple_el_contrato() -> None:
    with pytest.raises(ValidationError):
        sobre(occurred_at="2026-10-29T14:00:00")


def test_occurred_at_con_otra_zona_conserva_el_instante() -> None:
    bogota = sobre(occurred_at="2026-10-29T09:00:00-05:00")

    assert bogota.occurred_at == OCURRIO
    assert bogota.occurred_at.utcoffset() == timedelta(hours=-5)
