from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.api.dependencies import get_reloj, get_unit_of_work
from app.main import create_app
from tests.api.conftest import CON_CORRELACION, CORRELATION_ID
from tests.fakes import FakeUnitOfWork, reloj_fijo

URL = "/api/iam/register"
BODY: dict[str, Any] = {
    "email": "maria.perez@example.com",
    "password": "Tayrona2026",
    "nombre_completo": "María Pérez",
    "rol": "Turista",
    "habeas_data_aceptado": True,
    "es_mayor_de_edad": True,
}


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def client(uow: FakeUnitOfWork) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_unit_of_work] = lambda: uow
    app.dependency_overrides[get_reloj] = lambda: reloj_fijo
    with TestClient(app, headers=CON_CORRELACION) as c:
        yield c


def test_registro_201(client: TestClient, uow: FakeUnitOfWork) -> None:
    response = client.post(URL, json=BODY)

    assert response.status_code == 201
    data = response.json()
    assert set(data) == {
        "id",
        "email",
        "nombre_completo",
        "rol",
        "email_verificado",
        "idioma",
        "creado_en",
    }
    assert data["idioma"] == "es"
    assert data["email"] == "maria.perez@example.com"
    assert data["rol"] == "Turista"
    assert data["email_verificado"] is False
    assert "password_hash" not in data
    assert "password" not in data
    assert "Tayrona2026" not in response.text
    assert uow.commits == 1


def test_registro_duplicado_409(client: TestClient) -> None:
    assert client.post(URL, json=BODY).status_code == 201

    response = client.post(URL, json={**BODY, "email": "MARIA.PEREZ@example.com"})

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Ya existe una cuenta registrada con ese correo electrónico.",
        "code": "EMAIL_EN_USO",
        "correlation_id": CORRELATION_ID,
    }


@pytest.mark.parametrize(
    ("cambios", "code"),
    [
        ({"habeas_data_aceptado": False}, "HABEAS_DATA_REQUERIDO"),
        ({"es_mayor_de_edad": False}, "MAYORIA_DE_EDAD_REQUERIDA"),
        ({"password": "corta1"}, "PASSWORD_INVALIDA"),
        ({"password": "solamenteletras"}, "PASSWORD_INVALIDA"),
        ({"nombre_completo": " "}, "NOMBRE_INVALIDO"),
    ],
)
def test_reglas_de_dominio_422(
    client: TestClient, uow: FakeUnitOfWork, cambios: dict[str, Any], code: str
) -> None:
    response = client.post(URL, json={**BODY, **cambios})

    assert response.status_code == 422
    data = response.json()
    assert set(data) == {"detail", "code", "correlation_id"}
    assert data["code"] == code
    assert data["detail"]
    assert uow.commits == 0


def assert_validacion(response: Response, campos: set[str]) -> None:
    assert response.status_code == 422
    data = response.json()
    assert set(data) == {"detail", "code", "errores", "correlation_id"}
    assert data["detail"] == "Los datos enviados no son válidos."
    assert data["code"] == "VALIDACION"
    assert {e["campo"] for e in data["errores"]} == campos
    for error in data["errores"]:
        assert set(error) == {"campo", "mensaje"}  # sin input, ctx ni url
        assert error["mensaje"]


def test_email_mal_formado_422_validacion(client: TestClient) -> None:
    response = client.post(URL, json={**BODY, "email": "no-es-un-email"})

    assert_validacion(response, {"email"})


@pytest.mark.parametrize("rol", ["Admin", "Entidad"])
def test_rol_no_autorregistrable_422_validacion(client: TestClient, rol: str) -> None:
    # El Literal del esquema lo frena antes del caso de uso (que igual lanza ROL_NO_PERMITIDO).
    response = client.post(URL, json={**BODY, "rol": rol})

    assert_validacion(response, {"rol"})


def test_sin_password_422_validacion(client: TestClient) -> None:
    body = {k: v for k, v in BODY.items() if k != "password"}

    response = client.post(URL, json=body)

    assert_validacion(response, {"password"})


def test_422_validacion_no_repite_la_contrasena(client: TestClient, uow: FakeUnitOfWork) -> None:
    response = client.post(
        URL, json={**BODY, "email": "no-es-un-email", "password": "SuperSecreta123"}
    )

    assert_validacion(response, {"email"})
    assert "SuperSecreta123" not in response.text
    assert uow.commits == 0


def test_422_validacion_con_tipo_invalido_no_repite_el_valor(client: TestClient) -> None:
    # Un tipo inválido en el propio campo password es el caso en que Pydantic pondría
    # el valor en "input".
    response = client.post(URL, json={**BODY, "password": ["SuperSecreta123"]})

    assert_validacion(response, {"password"})
    assert "SuperSecreta123" not in response.text


def test_registro_con_idioma_en(client: TestClient, uow: FakeUnitOfWork) -> None:
    response = client.post(URL, json={**BODY, "idioma": "en"})

    assert response.status_code == 201
    assert response.json()["idioma"] == "en"
    assert uow.usuarios.por_email["maria.perez@example.com"].idioma.value == "en"


def test_idioma_no_soportado_422_validacion(client: TestClient) -> None:
    response = client.post(URL, json={**BODY, "idioma": "fr"})

    assert_validacion(response, {"idioma"})
