"""GET /internal/usuarios/{id}/contacto (C-15, contracts/openapi/iam-interno.yaml)."""

import logging
import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import Idioma
from tests.api.conftest import CORRELATION_ID, usuario
from tests.fakes import FakeUnitOfWork

NO_ENCONTRADO = {
    "detail": "El usuario no existe.",
    "code": "USUARIO_NO_ENCONTRADO",
    "correlation_id": CORRELATION_ID,
}
EMAIL = "maria.perez@example.com"


def url(usuario_id: uuid.UUID | str | None) -> str:
    return f"/internal/usuarios/{usuario_id}/contacto"


def consultas(resultado: str) -> float:
    valor = REGISTRY.get_sample_value("iam_contacto_consultas_total", {"resultado": resultado})
    return valor or 0.0


def campos_del_log(caplog: pytest.LogCaptureFixture) -> list[object]:
    return [
        getattr(r, "campos", None) for r in caplog.records if r.name == "app.api.routers.internal"
    ]


@pytest.fixture
def sembrado(uow: FakeUnitOfWork) -> Usuario:
    return uow.usuarios.sembrar(replace(usuario(), idioma=Idioma.EN))


def test_200_con_el_contrato(
    client: TestClient, sembrado: Usuario, caplog: pytest.LogCaptureFixture
) -> None:
    antes = consultas("ok")

    with caplog.at_level(logging.INFO):
        response = client.get(url(sembrado.id))

    assert response.status_code == 200
    assert response.json() == {
        "usuario_id": str(sembrado.id),
        "nombre": "María Pérez",
        "email": EMAIL,
        "idioma": "en",
    }
    assert consultas("ok") == antes + 1
    assert campos_del_log(caplog) == [{"usuario_id": sembrado.id, "resultado": "ok"}]
    assert EMAIL not in caplog.text


def test_usuario_inactivo_tambien_es_200(client: TestClient, uow: FakeUnitOfWork) -> None:
    inactivo = uow.usuarios.sembrar(replace(usuario(), activo=False))

    response = client.get(url(inactivo.id))

    assert response.status_code == 200
    assert response.json()["email"] == EMAIL


def test_usuario_inexistente_404(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    antes = consultas("no_encontrado")
    desconocido = uuid.uuid4()

    with caplog.at_level(logging.INFO):
        response = client.get(url(desconocido))

    assert response.status_code == 404
    assert response.json() == NO_ENCONTRADO
    assert consultas("no_encontrado") == antes + 1
    assert campos_del_log(caplog) == [{"usuario_id": desconocido, "resultado": "no_encontrado"}]


@pytest.mark.parametrize("cabecera", ["X-Forwarded-For", "X-Forwarded-Host"])
def test_por_traefik_es_404_aunque_el_usuario_exista(
    client: TestClient,
    uow: FakeUnitOfWork,
    sembrado: Usuario,
    cabecera: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    antes = consultas("rechazado_proxy")

    with caplog.at_level(logging.INFO):
        response = client.get(url(sembrado.id), headers={cabecera: "203.0.113.7"})

    # Igual que un usuario inexistente: no revela ni la ruta ni el usuario.
    assert response.status_code == 404
    assert response.json() == NO_ENCONTRADO
    assert uow.entradas == 0  # ni siquiera consulta la base
    assert consultas("rechazado_proxy") == antes + 1
    assert campos_del_log(caplog) == [{"usuario_id": sembrado.id, "resultado": "rechazado_proxy"}]


def test_por_traefik_con_uuid_mal_formado_tambien_es_404(client: TestClient) -> None:
    response = client.get(url("no-es-un-uuid"), headers={"X-Forwarded-For": "203.0.113.7"})

    assert response.status_code == 404
    assert response.json() == NO_ENCONTRADO


def test_uuid_mal_formado_422(client: TestClient, uow: FakeUnitOfWork) -> None:
    response = client.get(url("no-es-un-uuid"))

    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "VALIDACION"
    assert [e["campo"] for e in data["errores"]] == ["usuario_id"]
    assert uow.entradas == 0


def test_no_aparece_en_el_openapi(client: TestClient) -> None:
    rutas = client.get("/openapi.json").json()["paths"]

    assert not any(ruta.startswith("/internal") for ruta in rutas)
