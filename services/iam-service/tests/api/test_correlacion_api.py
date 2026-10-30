"""X-Correlation-ID: middleware, cuerpo de error y bitácora (C-05, C-12)."""

import re

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import CORRELATION_ID, unico_denegado
from tests.fakes import FakeUnitOfWork

VERIFICAR = "/api/iam/auth/verificar"
UUID4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def test_respeta_el_encabezado_recibido(client: TestClient, uow: FakeUnitOfWork) -> None:
    response = client.get(VERIFICAR)

    assert response.status_code == 401
    assert response.headers["X-Correlation-ID"] == CORRELATION_ID
    assert response.json()["correlation_id"] == CORRELATION_ID
    # La fila propia de la bitácora toma el de la petición.
    assert unico_denegado(uow).correlation_id == CORRELATION_ID


@pytest.mark.parametrize(
    "recibido",
    ["", "con espacios", "a" * 101, "comillas'y;otros"],
    ids=["vacio", "espacios", "muy_largo", "caracteres_no_permitidos"],
)
def test_genera_uno_nuevo_si_el_recibido_no_sirve(
    client: TestClient, uow: FakeUnitOfWork, recibido: str
) -> None:
    response = client.get(VERIFICAR, headers={"X-Correlation-ID": recibido})

    generado = response.headers["X-Correlation-ID"]
    assert UUID4.match(generado)
    assert response.json()["correlation_id"] == generado
    assert unico_denegado(uow).correlation_id == generado


def test_sin_encabezado_genera_uno_distinto_por_peticion(client: TestClient) -> None:
    del client.headers["X-Correlation-ID"]

    primero = client.get("/health/live").headers["X-Correlation-ID"]
    segundo = client.get("/health/live").headers["X-Correlation-ID"]

    assert UUID4.match(primero)
    assert UUID4.match(segundo)
    assert primero != segundo
