import uuid
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_almacen_documentos,
    get_enviador_correo,
    get_password_hasher,
    get_revocacion,
    get_tokens_recuperacion,
    get_unit_of_work,
)
from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import ResultadoAuditoria, Rol
from app.domain.value_objects.token import TokenEmitido
from app.infrastructure.security.jwt_token_service import JwtTokenService
from app.main import create_app
from tests.fakes import (
    AHORA,
    FakeAlmacenDocumentos,
    FakeEnviadorCorreo,
    FakePasswordHasher,
    FakeRevocacion,
    FakeTokensRecuperacion,
    FakeUnitOfWork,
    RegistroAuditoria,
)

# IP que reporta el TestClient: así se comprueba la columna ip_origen de la bitácora.
IP_CLIENTE = "190.24.10.5"
# X-Correlation-ID fijo en cada petición: los cuerpos de error se comparan completos (C-12).
CORRELATION_ID = "corr-prueba-api"
CON_CORRELACION = {"X-Correlation-ID": CORRELATION_ID}
TOKEN_INVALIDO = {
    "detail": "El token no es válido, expiró o fue revocado.",
    "code": "TOKEN_INVALIDO",
    "correlation_id": CORRELATION_ID,
}


def usuario(rol: Rol = Rol.TURISTA) -> Usuario:
    return Usuario(
        id=uuid.uuid4(),
        email="maria.perez@example.com",
        password_hash="x",
        nombre_completo="María Pérez",
        rol=rol,
        habeas_data_aceptado=True,
        habeas_data_aceptado_en=AHORA,
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def emitir(client: TestClient, rol: Rol = Rol.TURISTA) -> tuple[TokenEmitido, Usuario]:
    """Emite un token con el servicio de la app (mismas llaves) sin pasar por el login."""
    u = usuario(rol)
    tokens: JwtTokenService = client.app.state.token_service  # type: ignore[attr-defined]
    return tokens.emitir(u), u


def unico_denegado(uow: FakeUnitOfWork) -> RegistroAuditoria:
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("ACCESS_DENIED", ResultadoAuditoria.DENEGADO)
    assert registro.ip_origen == IP_CLIENTE
    return registro


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def revocacion() -> FakeRevocacion:
    return FakeRevocacion()


@pytest.fixture
def tokens_recuperacion() -> FakeTokensRecuperacion:
    return FakeTokensRecuperacion()


@pytest.fixture
def enviador() -> FakeEnviadorCorreo:
    return FakeEnviadorCorreo()


@pytest.fixture
def client(
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    tokens_recuperacion: FakeTokensRecuperacion,
    enviador: FakeEnviadorCorreo,
) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_unit_of_work] = lambda: uow
    app.dependency_overrides[get_revocacion] = lambda: revocacion
    app.dependency_overrides[get_tokens_recuperacion] = lambda: tokens_recuperacion
    app.dependency_overrides[get_enviador_correo] = lambda: enviador
    with TestClient(app, client=(IP_CLIENTE, 50000), headers=CON_CORRELACION) as c:
        yield c


@pytest.fixture
def hasher(client: TestClient) -> FakePasswordHasher:
    hasher = FakePasswordHasher()
    client.app.dependency_overrides[get_password_hasher] = lambda: hasher  # type: ignore[attr-defined]
    return hasher


@pytest.fixture
def almacen(client: TestClient) -> FakeAlmacenDocumentos:
    almacen = FakeAlmacenDocumentos()
    client.app.dependency_overrides[get_almacen_documentos] = lambda: almacen  # type: ignore[attr-defined]
    return almacen


CLAVE = "Actual12345"


def cuenta_con_sesion(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    rol: Rol = Rol.TURISTA,
    email: str = "maria.perez@example.com",
    **campos: Any,
) -> tuple[dict[str, str], Usuario]:
    """Siembra una cuenta con la contraseña CLAVE y emite su token."""
    guardado = uow.usuarios.sembrar(
        replace(usuario(rol), email=email, password_hash=hasher.hash(CLAVE), **campos)
    )
    tokens: JwtTokenService = client.app.state.token_service  # type: ignore[attr-defined]
    return bearer(tokens.emitir(guardado).access_token), guardado


def esperar_tareas(client: TestClient) -> None:
    """Espera lo que siguió corriendo después de responder (C-50)."""
    client.portal.call(client.app.state.tareas_segundo_plano.esperar)  # type: ignore[union-attr, attr-defined]
