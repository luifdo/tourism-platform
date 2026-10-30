import asyncio
import threading
import time

import pytest

from app.domain.exceptions import ServicioOcupadoError
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher


class HasherQueMide(Argon2PasswordHasher):
    """Registra cuántos cálculos corren a la vez y en qué hilo, sin gastar 64 MiB en cada uno."""

    def __init__(self, concurrencia_maxima: int, espera_maxima_segundos: float = 10.0) -> None:
        super().__init__(concurrencia_maxima, espera_maxima_segundos)
        self._candado = threading.Lock()
        self._activos = 0
        self.maximo = 0
        self.hilos: set[int] = set()

    def _medir(self) -> None:
        with self._candado:
            self._activos += 1
            self.maximo = max(self.maximo, self._activos)
            self.hilos.add(threading.get_ident())
        time.sleep(0.02)
        with self._candado:
            self._activos -= 1

    def hash(self, plain: str) -> str:
        self._medir()
        return "hash"

    def verify(self, plain: str, hashed: str) -> bool:
        self._medir()
        return True


async def test_el_semaforo_acota_los_calculos_simultaneos_entre_hash_y_verify() -> None:
    hasher = HasherQueMide(concurrencia_maxima=2)

    await asyncio.gather(
        *(hasher.hash_limitado("x") for _ in range(5)),
        *(hasher.verify_limitado("x", "h") for _ in range(5)),
    )

    assert hasher.maximo == 2


async def test_la_espera_agotada_es_servicio_ocupado_y_devuelve_el_cupo() -> None:
    hasher = HasherQueMide(concurrencia_maxima=1, espera_maxima_segundos=0.001)

    resultados = await asyncio.gather(
        hasher.hash_limitado("x"), hasher.verify_limitado("x", "h"), return_exceptions=True
    )

    assert resultados[0] == "hash"
    assert isinstance(resultados[1], ServicioOcupadoError)
    # Ni el que calculó ni el que se rindió se quedaron con el cupo.
    assert await hasher.hash_limitado("x") == "hash"


async def test_un_error_al_calcular_devuelve_el_cupo() -> None:
    class HasherQueFalla(Argon2PasswordHasher):
        def hash(self, plain: str) -> str:
            raise RuntimeError("fallo")

    hasher = HasherQueFalla(concurrencia_maxima=1, espera_maxima_segundos=0.05)

    for _ in range(2):  # el segundo daría ServicioOcupadoError si el cupo se hubiera perdido
        with pytest.raises(RuntimeError):
            await hasher.hash_limitado("x")


async def test_los_calculos_corren_fuera_del_hilo_del_bucle() -> None:
    hasher = HasherQueMide(concurrencia_maxima=4)

    await hasher.hash_limitado("x")
    await hasher.verify_limitado("x", "h")

    assert threading.get_ident() not in hasher.hilos


async def test_hash_y_verify_limitados_son_argon2_real() -> None:
    hasher = Argon2PasswordHasher()

    hashed = await hasher.hash_limitado("S3cret-turismo!")

    assert hashed.startswith("$argon2id$")
    assert await hasher.verify_limitado("S3cret-turismo!", hashed)
    assert not await hasher.verify_limitado("otra-clave", hashed)


def test_hash_and_verify_roundtrip() -> None:
    hasher = Argon2PasswordHasher()

    hashed = hasher.hash("S3cret-turismo!")

    assert hashed != "S3cret-turismo!"
    assert hasher.verify("S3cret-turismo!", hashed)


def test_verify_rejects_wrong_password() -> None:
    hasher = Argon2PasswordHasher()

    hashed = hasher.hash("S3cret-turismo!")

    assert not hasher.verify("otra-clave", hashed)


def test_hash_uses_argon2id() -> None:
    assert Argon2PasswordHasher().hash("S3cret-turismo!").startswith("$argon2id$")
