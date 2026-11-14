"""C-53: si la espera de Argon2 se agota, 503 SERVICIO_OCUPADO sin efectos sobre la cuenta."""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_password_hasher
from app.domain.exceptions import ServicioOcupadoError
from app.domain.value_objects.enums import ResultadoAuditoria
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher
from tests.api.conftest import CLAVE, CORRELATION_ID, cuenta_con_sesion, usuario
from tests.fakes import FakePasswordHasher, FakeRevocacion, FakeTokensRecuperacion, FakeUnitOfWork

LOGIN = "/api/iam/login"
RESTABLECER = "/api/iam/auth/restablecer"
PERFIL = "/api/iam/perfil"
EMAIL = "maria.perez@example.com"
NUEVA = "Nueva12345"
OCUPADO = {
    "detail": "El servicio está ocupado. Intente de nuevo en unos segundos.",
    "code": "SERVICIO_OCUPADO",
    "correlation_id": CORRELATION_ID,
}


class HasherSinCupo(FakePasswordHasher):
    """Como el real cuando la espera se agota: `hash` sí sirve para sembrar cuentas."""

    async def hash_limitado(self, plain: str) -> str:
        raise ServicioOcupadoError()

    async def verify_limitado(self, plain: str, hashed: str) -> bool:
        raise ServicioOcupadoError()


class HasherQueRetiene(Argon2PasswordHasher):
    """El semáforo real con un `verify` que no termina hasta que la prueba lo suelta."""

    def __init__(self) -> None:
        super().__init__(concurrencia_maxima=1, espera_maxima_segundos=0.05)
        self.soltar = threading.Event()
        self.en_curso = threading.Event()

    def verify(self, plain: str, hashed: str) -> bool:
        self.en_curso.set()
        self.soltar.wait(timeout=8)
        return True

    def needs_rehash(self, hashed: str) -> bool:
        return False


@pytest.fixture
def sin_cupo(client: TestClient) -> HasherSinCupo:
    hasher = HasherSinCupo()
    client.app.dependency_overrides[get_password_hasher] = lambda: hasher  # type: ignore[attr-defined]
    return hasher


def assert_ocupado(response) -> None:  # type: ignore[no-untyped-def]
    assert response.status_code == 503
    assert response.json() == OCUPADO
    assert response.headers["Retry-After"] == "2"


def test_login_que_agota_la_espera_es_503_y_no_cuenta_como_login_fail(
    client: TestClient, uow: FakeUnitOfWork
) -> None:
    uow.usuarios.sembrar(replace(usuario(), email=EMAIL, password_hash="x"))
    hasher = HasherQueRetiene()
    client.app.dependency_overrides[get_password_hasher] = lambda: hasher  # type: ignore[attr-defined]
    cuerpo = {"email": EMAIL, "password": CLAVE}

    with ThreadPoolExecutor(max_workers=1) as pool:
        primero = pool.submit(client.post, LOGIN, json=cuerpo)
        assert hasher.en_curso.wait(timeout=5)

        rechazado = client.post(LOGIN, json=cuerpo)

        assert_ocupado(rechazado)
        assert not primero.done()
        assert uow.auditoria.registros == []  # ni LOGIN_FAIL ni ninguna otra fila

        hasher.soltar.set()
        assert primero.result(timeout=5).status_code == 200

    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("LOGIN_SUCCESS", ResultadoAuditoria.EXITO)
    # El cupo volvió: el que esperó de más no se lo quedó.
    assert client.post(LOGIN, json=cuerpo).status_code == 200


def test_login_de_un_correo_inexistente_responde_igual(
    client: TestClient, uow: FakeUnitOfWork, sin_cupo: HasherSinCupo
) -> None:
    assert_ocupado(client.post(LOGIN, json={"email": "nadie@example.com", "password": CLAVE}))
    assert uow.auditoria.registros == []


def test_registro_ocupado_no_crea_la_cuenta(
    client: TestClient, uow: FakeUnitOfWork, sin_cupo: HasherSinCupo
) -> None:
    response = client.post(
        "/api/iam/register",
        json={
            "email": EMAIL,
            "password": CLAVE,
            "nombre_completo": "María Pérez",
            "rol": "Turista",
            "habeas_data_aceptado": True,
            "es_mayor_de_edad": True,
        },
    )

    assert_ocupado(response)
    assert uow.usuarios.por_email == {}
    assert uow.auditoria.registros == []


def test_restablecer_ocupado_no_gasta_el_enlace_y_el_reintento_funciona(
    client: TestClient,
    uow: FakeUnitOfWork,
    sin_cupo: HasherSinCupo,
    tokens_recuperacion: FakeTokensRecuperacion,
) -> None:
    u = uow.usuarios.sembrar(replace(usuario(), email=EMAIL, password_hash=sin_cupo.hash(CLAVE)))
    tokens_recuperacion.tokens["enlace"] = u.id  # type: ignore[assignment]
    cuerpo = {"token": "enlace", "password": NUEVA}

    assert_ocupado(client.post(RESTABLECER, json=cuerpo))
    assert "enlace" in tokens_recuperacion.tokens
    assert uow.auditoria.registros == []

    con_cupo = FakePasswordHasher()
    client.app.dependency_overrides[get_password_hasher] = lambda: con_cupo  # type: ignore[attr-defined]
    assert client.post(RESTABLECER, json=cuerpo).status_code == 204
    assert "enlace" not in tokens_recuperacion.tokens


def test_restablecer_con_token_falso_es_400_sin_gastar_argon2(
    client: TestClient, sin_cupo: HasherSinCupo
) -> None:
    # Si intentara calcular, este hasher respondería 503.
    response = client.post(RESTABLECER, json={"token": "falso", "password": NUEVA})

    assert response.status_code == 400
    assert response.json()["code"] == "TOKEN_INVALIDO"


def test_dos_restablecer_con_el_mismo_enlace_solo_uno_sigue(
    client: TestClient,
    uow: FakeUnitOfWork,
    tokens_recuperacion: FakeTokensRecuperacion,
) -> None:
    """El otro consumió el enlace mientras este calculaba el hash."""
    u = uow.usuarios.sembrar(replace(usuario(), email=EMAIL, password_hash="x"))
    tokens_recuperacion.tokens["enlace"] = u.id  # type: ignore[assignment]

    class HasherAdelantado(FakePasswordHasher):
        async def hash_limitado(self, plain: str) -> str:
            tokens_recuperacion.tokens.pop("enlace")
            return self.hash(plain)

    hasher = HasherAdelantado()
    client.app.dependency_overrides[get_password_hasher] = lambda: hasher  # type: ignore[attr-defined]

    response = client.post(RESTABLECER, json={"token": "enlace", "password": NUEVA})

    assert response.status_code == 400
    assert uow.auditoria.registros == []


def test_cambio_de_contrasena_ocupado_no_cambia_ni_revoca(
    client: TestClient, uow: FakeUnitOfWork, revocacion: FakeRevocacion, sin_cupo: HasherSinCupo
) -> None:
    cabeceras, cuenta = cuenta_con_sesion(client, uow, sin_cupo)

    response = client.post(
        f"{PERFIL}/contrasena",
        json={"password_actual": CLAVE, "password_nueva": NUEVA},
        headers=cabeceras,
    )

    assert_ocupado(response)
    assert uow.usuarios.por_email[cuenta.email].password_hash == cuenta.password_hash
    assert revocacion.revocados == {}
    assert uow.auditoria.registros == []


def test_supresion_ocupada_no_borra_ni_revoca(
    client: TestClient, uow: FakeUnitOfWork, revocacion: FakeRevocacion, sin_cupo: HasherSinCupo
) -> None:
    cabeceras, cuenta = cuenta_con_sesion(client, uow, sin_cupo)

    response = client.request("DELETE", PERFIL, json={"password": CLAVE}, headers=cabeceras)

    assert_ocupado(response)
    assert uow.usuarios.por_email[cuenta.email].suprimido is False
    assert revocacion.revocados == {}
    assert uow.auditoria.registros == []
