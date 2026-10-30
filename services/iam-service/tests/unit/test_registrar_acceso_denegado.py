import logging
import uuid

import pytest

from app.application.use_cases.registrar_acceso_denegado import RegistrarAccesoDenegado
from app.domain.value_objects.enums import ResultadoAuditoria
from tests.fakes import FakeUnitOfWork


async def test_inserta_access_denied_en_su_propia_transaccion() -> None:
    uow = FakeUnitOfWork()
    usuario_id = uuid.uuid4()
    detalles = {"motivo": "revocado", "metodo": "GET", "uri": "/api/catalog/servicios"}

    await RegistrarAccesoDenegado(uow).execute(usuario_id, "190.0.0.1", detalles)

    assert uow.commits == 1
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("ACCESS_DENIED", ResultadoAuditoria.DENEGADO)
    assert (registro.usuario_id, registro.ip_origen, registro.detalles) == (
        usuario_id,
        "190.0.0.1",
        detalles,
    )


async def test_si_la_bitacora_falla_registra_el_error_y_no_propaga(
    caplog: pytest.LogCaptureFixture,
) -> None:
    uow = FakeUnitOfWork(caida=True)

    with caplog.at_level(logging.ERROR):
        await RegistrarAccesoDenegado(uow).execute(None, None, {"motivo": "sin_token"})

    assert "No se pudo registrar ACCESS_DENIED" in caplog.text
    assert "ConnectionRefusedError" in caplog.text
    assert uow.auditoria.registros == []
