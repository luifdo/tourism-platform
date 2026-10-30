"""C-59: con un S3 que acepta conexiones y no responde, el 503 llega a tiempo y el login sigue."""

import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_almacen_documentos
from app.config import get_settings
from app.domain.value_objects.enums import Rol
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.security.jwt_token_service import JwtTokenService
from app.infrastructure.storage.almacen_documentos_s3 import AlmacenDocumentosS3
from tests.api.conftest import bearer, usuario
from tests.fakes import FakeUnitOfWork, ServidorMudo
from tests.unit.test_documentos_dominio import PDF

DOCUMENTOS = "/api/iam/prestador/documentos"
LOGIN = "/api/iam/login"
PASSWORD = "Tayrona2026"
MAXIMO_503 = 10.0
# Holgado para una máquina de CI ocupada, y muy por debajo de lo que tarda el 503.
MAXIMO_POR_LOGIN = 2.0


@pytest.fixture
def servidor(client: TestClient) -> Iterator[ServidorMudo]:
    s = get_settings()
    with ServidorMudo() as mudo:
        almacen = AlmacenDocumentosS3(
            endpoint_interno=mudo.url,
            endpoint_publico=mudo.url,
            region="us-east-1",
            access_key="x",
            secret_key="y",
            bucket="sin-respuesta",
            hilos_maximos=s.s3_hilos_maximos,
            tiempo_maximo_segundos=s.s3_tiempo_maximo_segundos,
        )
        client.app.dependency_overrides[get_almacen_documentos] = lambda: almacen  # type: ignore[attr-defined]
        yield mudo
        almacen.cerrar()


@pytest.fixture
def sesion(client: TestClient, uow: FakeUnitOfWork) -> dict[str, str]:
    cuenta = uow.usuarios.sembrar(
        replace(usuario(Rol.PRESTADOR), password_hash=Argon2PasswordHasher().hash(PASSWORD))
    )
    tokens: JwtTokenService = client.app.state.token_service  # type: ignore[attr-defined]
    return bearer(tokens.emitir(cuenta).access_token)


def _subir(client: TestClient, sesion: dict[str, str]) -> tuple[int, float]:
    inicio = time.monotonic()
    respuesta = client.post(
        DOCUMENTOS,
        data={"tipo": "RNT"},
        files={"archivo": ("rnt.pdf", PDF, "application/pdf")},
        headers=sesion,
    )
    return respuesta.status_code, time.monotonic() - inicio


def _login(client: TestClient) -> tuple[int, float]:
    inicio = time.monotonic()
    respuesta = client.post(LOGIN, json={"email": "maria.perez@example.com", "password": PASSWORD})
    return respuesta.status_code, time.monotonic() - inicio


def test_con_todos_los_hilos_de_s3_ocupados_el_login_sigue_y_la_carga_da_503_a_tiempo(
    client: TestClient, servidor: ServidorMudo, sesion: dict[str, str]
) -> None:
    hilos = get_settings().s3_hilos_maximos
    # Uno más que los hilos: ese espera turno y también debe recibir su 503 a tiempo.
    with ThreadPoolExecutor(max_workers=hilos + 1) as pool:
        cargas = [pool.submit(_subir, client, sesion) for _ in range(hilos + 1)]
        assert servidor.esperar_conexiones(hilos, timeout=5)

        for _ in range(3):
            codigo, duracion = _login(client)
            assert codigo == 200
            assert duracion < MAXIMO_POR_LOGIN
        assert not any(carga.done() for carga in cargas)  # el login pasó con S3 todavía colgado

        resultados = [carga.result(timeout=MAXIMO_503 + 5) for carga in cargas]

    assert [codigo for codigo, _ in resultados] == [503] * (hilos + 1)
    assert max(duracion for _, duracion in resultados) < MAXIMO_503
    # Los hilos siguen ocupados con sus reintentos: el login no depende de ellos.
    codigo, duracion = _login(client)
    assert (codigo, duracion < MAXIMO_POR_LOGIN) == (200, True)


def test_la_supresion_da_503_a_tiempo_sin_cambiar_la_cuenta(
    client: TestClient, uow: FakeUnitOfWork, servidor: ServidorMudo, sesion: dict[str, str]
) -> None:
    inicio = time.monotonic()
    respuesta = client.request(
        "DELETE", "/api/iam/perfil", json={"password": PASSWORD}, headers=sesion
    )

    assert respuesta.status_code == 503
    assert respuesta.json()["code"] == "SERVICIO_NO_DISPONIBLE"
    assert time.monotonic() - inicio < MAXIMO_503
    assert servidor.esperar_conexiones(1, timeout=1)
    assert not [r for r in uow.auditoria.registros if r.accion == "DATA_SUPPRESSION"]
