"""C-53: con hashes en curso o en cola, la réplica sigue respondiendo sus sondas y a verificar."""

import threading
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_password_hasher
from app.domain.value_objects.enums import Rol
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher
from tests.api.conftest import bearer, emitir, usuario
from tests.fakes import FakeUnitOfWork

LOGIN = "/api/iam/login"
PASSWORD = "Tayrona2026"
# Sin el hash en un hilo, las peticiones de abajo tardarían todo este tiempo, y el login ya
# habría terminado cuando respondan.
ESPERA_DEL_HASH = 8.0
# Muy por debajo de ESPERA_DEL_HASH; holgado para una máquina de CI ocupada.
MAXIMO_POR_PETICION = 2.0


class HasherLento(Argon2PasswordHasher):
    """El Argon2 real con un `verify` que no termina hasta que la prueba lo suelta."""

    def __init__(self, concurrencia_maxima: int, espera_maxima_segundos: float = 10.0) -> None:
        super().__init__(concurrencia_maxima, espera_maxima_segundos)
        self.soltar = threading.Event()
        self.en_curso = threading.Semaphore(0)

    def verify(self, plain: str, hashed: str) -> bool:
        self.en_curso.release()
        self.soltar.wait(timeout=ESPERA_DEL_HASH)
        return True

    def needs_rehash(self, hashed: str) -> bool:
        return False


class UowQueCuentaAbiertas(FakeUnitOfWork):
    """Cuenta las transacciones abiertas, como las conexiones que ocuparían del pool."""

    def __init__(self) -> None:
        super().__init__()
        self.abiertas = 0

    async def __aenter__(self) -> "UowQueCuentaAbiertas":
        await super().__aenter__()
        self.abiertas += 1
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.abiertas -= 1
        await super().__aexit__(*exc)  # type: ignore[arg-type]


@pytest.fixture
def uow() -> UowQueCuentaAbiertas:
    uow = UowQueCuentaAbiertas()
    uow.usuarios.sembrar(replace(usuario(), password_hash="x"))
    return uow


@pytest.fixture
def lento(client: TestClient) -> Iterator[HasherLento]:
    # Un solo cupo: el segundo login se queda esperando el semáforo.
    hasher = HasherLento(concurrencia_maxima=1)
    client.app.dependency_overrides[get_password_hasher] = lambda: hasher  # type: ignore[attr-defined]
    yield hasher
    hasher.soltar.set()


def _login(client: TestClient) -> int:
    return client.post(
        LOGIN, json={"email": "maria.perez@example.com", "password": PASSWORD}
    ).status_code


def _responde_pronto(client: TestClient, ruta: str, **kwargs: object) -> int:
    inicio = time.monotonic()
    respuesta = client.get(ruta, **kwargs)  # type: ignore[arg-type]
    assert time.monotonic() - inicio < MAXIMO_POR_PETICION
    return respuesta.status_code


def _lanzar_login(pool: ThreadPoolExecutor, client: TestClient) -> Future[int]:
    return pool.submit(_login, client)


def test_sondas_y_verificar_responden_con_un_login_en_curso(
    client: TestClient, lento: HasherLento
) -> None:
    token, _ = emitir(client, Rol.TURISTA)

    with ThreadPoolExecutor(max_workers=1) as pool:
        login = _lanzar_login(pool, client)
        assert lento.en_curso.acquire(timeout=5)

        assert _responde_pronto(client, "/health/live") == 200
        assert (
            _responde_pronto(client, "/api/iam/auth/verificar", headers=bearer(token.access_token))
            == 200
        )
        assert not login.done()  # todo lo anterior pasó con el hash sin terminar

        lento.soltar.set()
        assert login.result(timeout=5) == 200


def test_quien_espera_el_semaforo_no_bloquea_ni_ocupa_una_conexion(
    client: TestClient, lento: HasherLento, uow: UowQueCuentaAbiertas
) -> None:
    token, _ = emitir(client, Rol.TURISTA)

    with ThreadPoolExecutor(max_workers=2) as pool:
        primero = _lanzar_login(pool, client)
        assert lento.en_curso.acquire(timeout=5)
        segundo = _lanzar_login(pool, client)
        # Cada login abre una transacción para leer la cuenta y luego va al semáforo.
        limite = time.monotonic() + 5
        while uow.entradas < 2 and time.monotonic() < limite:
            time.sleep(0.01)
        assert uow.entradas == 2

        assert not lento.en_curso.acquire(timeout=0.2)  # no entró a calcular: no hay cupo
        assert uow.abiertas == 0  # ni el que calcula ni el que espera retienen una conexión
        assert _responde_pronto(client, "/health/live") == 200
        assert (
            _responde_pronto(client, "/api/iam/auth/verificar", headers=bearer(token.access_token))
            == 200
        )
        assert not primero.done() and not segundo.done()

        lento.soltar.set()
        assert primero.result(timeout=5) == 200
        assert segundo.result(timeout=5) == 200
