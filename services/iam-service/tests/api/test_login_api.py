from collections.abc import Iterator

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_revocacion, get_unit_of_work
from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import ResultadoAuditoria, Rol
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher
from app.main import create_app
from tests.api.conftest import CON_CORRELACION, CORRELATION_ID
from tests.fakes import AHORA, FakeRevocacion, FakeUnitOfWork

LOGIN = "/api/iam/login"
LOGOUT = "/api/iam/logout"
JWKS = "/api/iam/.well-known/jwks.json"
PASSWORD = "Tayrona2026"
HASH = Argon2PasswordHasher().hash(PASSWORD)
CREDENCIALES_INVALIDAS = {
    "detail": "Correo o contraseña incorrectos.",
    "code": "CREDENCIALES_INVALIDAS",
    "correlation_id": CORRELATION_ID,
}


def sembrar(uow: FakeUnitOfWork, email: str, activo: bool = True) -> Usuario:
    return uow.usuarios.sembrar(
        Usuario(
            email=email,
            password_hash=HASH,
            nombre_completo="María Pérez",
            rol=Rol.TURISTA,
            activo=activo,
            habeas_data_aceptado=True,
            habeas_data_aceptado_en=AHORA,
        )
    )


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    sembrar(uow, "maria.perez@example.com")
    sembrar(uow, "inactiva@example.com", activo=False)
    return uow


@pytest.fixture
def revocacion() -> FakeRevocacion:
    return FakeRevocacion()


@pytest.fixture
def client(uow: FakeUnitOfWork, revocacion: FakeRevocacion) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_unit_of_work] = lambda: uow
    app.dependency_overrides[get_revocacion] = lambda: revocacion
    with TestClient(app, headers=CON_CORRELACION) as c:
        yield c


def login(client: TestClient, email: str = "maria.perez@example.com") -> str:
    response = client.post(LOGIN, json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_200(client: TestClient) -> None:
    response = client.post(LOGIN, json={"email": "Maria.Perez@Example.com", "password": PASSWORD})

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"access_token", "token_type", "expires_in", "usuario"}
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900
    assert set(data["usuario"]) == {
        "id",
        "email",
        "nombre_completo",
        "rol",
        "email_verificado",
        "idioma",
        "creado_en",
    }
    assert data["usuario"]["email"] == "maria.perez@example.com"
    assert PASSWORD not in response.text
    assert jwt.get_unverified_header(data["access_token"])["alg"] == "RS256"


@pytest.mark.parametrize(
    "credenciales",
    [
        {"email": "maria.perez@example.com", "password": "Incorrecta123"},
        {"email": "nadie@example.com", "password": PASSWORD},
        {"email": "no-es-un-email", "password": PASSWORD},
    ],
    ids=["password_incorrecta", "usuario_no_existe", "email_mal_formado"],
)
def test_login_401_mismo_cuerpo(client: TestClient, credenciales: dict[str, str]) -> None:
    response = client.post(LOGIN, json=credenciales)

    assert response.status_code == 401
    assert response.json() == CREDENCIALES_INVALIDAS
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_login_401_cuerpos_identicos_byte_a_byte(client: TestClient) -> None:
    incorrecta = client.post(
        LOGIN, json={"email": "maria.perez@example.com", "password": "Incorrecta123"}
    )
    inexistente = client.post(LOGIN, json={"email": "nadie@example.com", "password": PASSWORD})

    assert incorrecta.content == inexistente.content


def test_login_403_cuenta_inactiva(client: TestClient) -> None:
    response = client.post(LOGIN, json={"email": "inactiva@example.com", "password": PASSWORD})

    assert response.status_code == 403
    assert response.json() == {
        "detail": "La cuenta está desactivada. Contacte al administrador.",
        "code": "CUENTA_INACTIVA",
        "correlation_id": CORRELATION_ID,
    }


def test_logout_204_y_luego_401(client: TestClient, revocacion: FakeRevocacion) -> None:
    token = login(client)

    primero = client.post(LOGOUT, headers=bearer(token))
    segundo = client.post(LOGOUT, headers=bearer(token))

    assert primero.status_code == 204
    assert primero.content == b""
    assert len(revocacion.revocados) == 1
    assert segundo.status_code == 401
    assert segundo.json()["code"] == "TOKEN_INVALIDO"
    assert segundo.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    ("headers", "motivo"),
    [
        ({}, "sin_token"),
        ({"Authorization": "Bearer no-es-un-jwt"}, "invalido"),
        ({"Authorization": "Basic dXNlcjpwYXNz"}, "sin_token"),
    ],
    ids=["sin_token", "token_basura", "otro_esquema"],
)
def test_logout_401(
    client: TestClient, uow: FakeUnitOfWork, headers: dict[str, str], motivo: str
) -> None:
    response = client.post(LOGOUT, headers=headers)

    assert response.status_code == 401
    assert response.json() == {
        "detail": "El token no es válido, expiró o fue revocado.",
        "code": "TOKEN_INVALIDO",
        "correlation_id": CORRELATION_ID,
    }
    assert response.headers["WWW-Authenticate"] == "Bearer"
    # ESC-04: el 401 del logout también queda en la bitácora.
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("ACCESS_DENIED", ResultadoAuditoria.DENEGADO)
    assert registro.usuario_id is None
    assert registro.detalles == {"motivo": motivo, "metodo": "POST", "uri": LOGOUT}


def test_logout_con_token_revocado_audita_con_el_usuario(
    client: TestClient, uow: FakeUnitOfWork
) -> None:
    token = login(client)
    client.post(LOGOUT, headers=bearer(token))

    response = client.post(LOGOUT, headers=bearer(token))

    assert response.status_code == 401
    usuario = uow.usuarios.por_email["maria.perez@example.com"]
    acciones = [(r.accion, r.usuario_id) for r in uow.auditoria.registros]
    assert acciones == [
        ("LOGIN_SUCCESS", usuario.id),
        ("LOGOUT", usuario.id),
        ("ACCESS_DENIED", usuario.id),
    ]
    assert uow.auditoria.registros[-1].detalles["motivo"] == "revocado"


def test_logout_503_si_valkey_no_responde(client: TestClient, revocacion: FakeRevocacion) -> None:
    token = login(client)
    revocacion.caida = True

    response = client.post(LOGOUT, headers=bearer(token))

    assert response.status_code == 503
    assert response.json()["code"] == "SERVICIO_NO_DISPONIBLE"


def test_jwks(client: TestClient) -> None:
    token = login(client)

    response = client.get(JWKS)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=300"
    [jwk] = response.json()["keys"]
    assert jwk["kid"] == jwt.get_unverified_header(token)["kid"]
    jwt.decode(token, jwt.PyJWK(jwk).key, algorithms=["RS256"], issuer="iam-service")
