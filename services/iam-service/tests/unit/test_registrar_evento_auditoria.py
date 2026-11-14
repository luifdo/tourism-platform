import uuid
from dataclasses import replace
from datetime import timedelta

import pytest

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.registrar_evento_auditoria import RegistrarEventoAuditoria
from app.domain.value_objects.enums import ResultadoAuditoria
from app.domain.value_objects.evento_auditoria import EventoAuditoria
from tests.fakes import AHORA, FakeUnitOfWork


def evento(**cambios: object) -> EventoAuditoria:
    base = EventoAuditoria(
        event_id=uuid.uuid4(),
        servicio_origen="catalog-service",
        ocurrido_en=AHORA - timedelta(hours=1),
        accion="ZONA_CREADA",
        resultado=ResultadoAuditoria.EXITO,
        usuario_id=uuid.uuid4(),
        ip_origen="181.49.10.7",
        detalles={"zona_id": "z-1"},
        correlation_id="corr-1",
    )
    return replace(base, **cambios)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def caso(uow: FakeUnitOfWork) -> RegistrarEventoAuditoria:
    return RegistrarEventoAuditoria(lambda: uow)


async def test_guarda_el_evento_tal_cual_y_confirma(
    caso: RegistrarEventoAuditoria, uow: FakeUnitOfWork
) -> None:
    recibido = evento()

    assert await caso.execute(recibido) is ResultadoConsumo.APLICADO

    assert uow.auditoria.eventos == {recibido.event_id: recibido}
    assert uow.commits == 1


async def test_el_mismo_event_id_otra_vez_es_duplicado(
    caso: RegistrarEventoAuditoria, uow: FakeUnitOfWork
) -> None:
    recibido = evento()
    await caso.execute(recibido)

    assert await caso.execute(recibido) is ResultadoConsumo.DUPLICADO
    assert len(uow.auditoria.eventos) == 1


@pytest.mark.parametrize("ip", ["181.49.10.7", "2800:e2:2780:1::7", None])
async def test_ip_valida_o_ausente_no_cambia(
    caso: RegistrarEventoAuditoria, uow: FakeUnitOfWork, ip: str | None
) -> None:
    recibido = evento(ip_origen=ip)

    await caso.execute(recibido)

    assert uow.auditoria.eventos[recibido.event_id] == recibido


@pytest.mark.parametrize("ip", ["no-es-ip", "999.1.1.1", "10.0.0.0/8", "fe80::1%eth0", ""])
async def test_ip_invalida_queda_nula_y_su_texto_en_detalles(
    caso: RegistrarEventoAuditoria, uow: FakeUnitOfWork, ip: str
) -> None:
    recibido = evento(ip_origen=ip)

    assert await caso.execute(recibido) is ResultadoConsumo.APLICADO

    guardado = uow.auditoria.eventos[recibido.event_id]
    assert guardado.ip_origen is None
    assert guardado.detalles == {"zona_id": "z-1", "ip_origen_invalida": ip}
    assert recibido.detalles == {"zona_id": "z-1"}  # no se modifica el original


async def test_un_error_de_la_base_se_propaga_para_reintentar() -> None:
    caso = RegistrarEventoAuditoria(lambda: FakeUnitOfWork(caida=True))

    with pytest.raises(ConnectionRefusedError):
        await caso.execute(evento())
