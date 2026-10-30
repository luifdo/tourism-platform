import asyncio
import logging
from collections.abc import Callable

from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import InvalidHashError, VerificationError

from app.domain.exceptions import ServicioOcupadoError

logger = logging.getLogger(__name__)


class Argon2PasswordHasher:
    """Implementa PasswordHasher con Argon2id y los parámetros por defecto de argon2-cffi.

    Cada cálculo reserva 64 MiB. El semáforo acota la memoria de la réplica y, como es de
    asyncio, quien espera su turno no ocupa un hilo ni frena el bucle de eventos. La espera
    tiene tope: si se pasa, ServicioOcupadoError en vez de seguir en cola (C-53).
    """

    def __init__(self, concurrencia_maxima: int = 4, espera_maxima_segundos: float = 10.0) -> None:
        self._argon2 = _Argon2()
        self._cupos = asyncio.Semaphore(concurrencia_maxima)
        self._espera_maxima = espera_maxima_segundos

    def hash(self, plain: str) -> str:
        return self._argon2.hash(plain)

    def verify(self, plain: str, hashed: str) -> bool:
        try:
            return self._argon2.verify(hashed, plain)
        except (VerificationError, InvalidHashError):
            return False

    async def hash_limitado(self, plain: str) -> str:
        return await self._con_cupo(self.hash, plain)

    async def verify_limitado(self, plain: str, hashed: str) -> bool:
        return await self._con_cupo(self.verify, plain, hashed)

    def needs_rehash(self, hashed: str) -> bool:
        return self._argon2.check_needs_rehash(hashed)

    async def _con_cupo[T](self, calculo: Callable[..., T], *args: str) -> T:
        try:
            async with asyncio.timeout(self._espera_maxima):
                await self._cupos.acquire()
        except TimeoutError:
            logger.warning("Espera de Argon2 agotada: se responde SERVICIO_OCUPADO")
            raise ServicioOcupadoError() from None
        try:
            return await asyncio.to_thread(calculo, *args)
        finally:
            self._cupos.release()
