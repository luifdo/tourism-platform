"""Dobles en memoria de los puertos, para probar sin base de datos."""

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self

from redis.exceptions import ConnectionError as RedisConnectionError

from app.domain.entities.usuario import Usuario
from app.domain.exceptions import ServicioNoDisponibleError, UsuarioYaExisteError
from app.domain.value_objects.email import Email
from app.domain.value_objects.enums import ResultadoAuditoria

AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)


def reloj_fijo() -> datetime:
    return AHORA


class FakeUsuarioRepository:
    def __init__(self) -> None:
        self.por_email: dict[str, Usuario] = {}

    async def add(self, usuario: Usuario) -> Usuario:
        if usuario.email in self.por_email:
            raise UsuarioYaExisteError()
        guardado = replace(usuario, id=uuid.uuid4(), creado_en=AHORA, actualizado_en=AHORA)
        self.por_email[usuario.email] = guardado
        return guardado

    async def find_by_email(self, email: Email) -> Usuario | None:
        return self.por_email.get(email.value)

    async def actualizar_password_hash(self, usuario_id: uuid.UUID, password_hash: str) -> None:
        for email, usuario in self.por_email.items():
            if usuario.id == usuario_id:
                self.por_email[email] = replace(usuario, password_hash=password_hash)

    def sembrar(self, usuario: Usuario) -> Usuario:
        """Guarda un usuario ya existente (sin pasar por el caso de uso de registro)."""
        guardado = replace(usuario, id=uuid.uuid4(), creado_en=AHORA, actualizado_en=AHORA)
        self.por_email[guardado.email] = guardado
        return guardado


class FakePasswordHasher:
    """Hasher trivial que registra cada verify (para comprobar el verify de relleno).

    Como Argon2, el hash lleva sus "parámetros" (version): un hash de otra versión
    sigue verificando, pero needs_rehash() devuelve True.
    """

    def __init__(self, version: int = 1) -> None:
        self.version = version
        self.verificados: list[str] = []

    def hash(self, plain: str) -> str:
        return f"fake-hash:v{self.version}:{plain[::-1]}"

    def verify(self, plain: str, hashed: str) -> bool:
        self.verificados.append(hashed)
        prefijo, _, resto = hashed.partition(":")
        _, _, invertida = resto.partition(":")
        return prefijo == "fake-hash" and invertida == plain[::-1]

    def needs_rehash(self, hashed: str) -> bool:
        return not hashed.startswith(f"fake-hash:v{self.version}:")


class FakeRevocacion:
    """Lista de revocación en memoria. caida=True simula Valkey sin responder."""

    def __init__(self, caida: bool = False) -> None:
        self.revocados: dict[str, datetime] = {}
        self.revocados_desde: dict[uuid.UUID, int] = {}
        self.caida = caida

    async def revocar(self, jti: str, expira_en: datetime) -> None:
        if self.caida:
            raise ServicioNoDisponibleError()
        self.revocados[jti] = expira_en

    async def revocar_usuario(self, usuario_id: uuid.UUID, desde: datetime) -> None:
        if self.caida:
            raise ServicioNoDisponibleError()
        self.revocados_desde[usuario_id] = int(desde.timestamp())

    async def esta_revocado_token(self, jti: str, usuario_id: uuid.UUID, iat: datetime) -> bool:
        if self.caida:
            raise ServicioNoDisponibleError()
        desde = self.revocados_desde.get(usuario_id)
        return jti in self.revocados or (desde is not None and int(iat.timestamp()) <= desde)


class FakeRedisClient:
    """Lo mínimo de redis.asyncio.Redis que usa ValkeyRevocacionTokens (sin expiración real)."""

    def __init__(self, caido: bool = False) -> None:
        self.valores: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.llamadas_mget = 0
        self.caido = caido

    def _comprobar(self) -> None:
        if self.caido:
            raise RedisConnectionError("Valkey caído")

    async def set(self, key: str, value: Any, ex: int) -> None:
        self._comprobar()
        self.valores[key] = str(value)
        self.ttls[key] = ex

    async def mget(self, *keys: str) -> list[str | None]:
        self._comprobar()
        self.llamadas_mget += 1
        return [self.valores.get(key) for key in keys]


@dataclass
class RegistroAuditoria:
    accion: str
    resultado: ResultadoAuditoria
    usuario_id: uuid.UUID | None
    ip_origen: str | None
    detalles: dict[str, Any]


class FakeAuditoriaRepository:
    def __init__(self) -> None:
        self.registros: list[RegistroAuditoria] = []

    async def registrar(
        self,
        accion: str,
        resultado: ResultadoAuditoria,
        usuario_id: uuid.UUID | None,
        ip_origen: str | None,
        detalles: dict[str, Any],
    ) -> None:
        self.registros.append(RegistroAuditoria(accion, resultado, usuario_id, ip_origen, detalles))


class FakeUnitOfWork:
    """Cuenta entradas, commits y rollbacks. Los repositorios persisten entre usos, como una
    base real. caida=True simula PostgreSQL sin responder al abrir la transacción.
    """

    def __init__(self, caida: bool = False) -> None:
        self.usuarios = FakeUsuarioRepository()
        self.auditoria = FakeAuditoriaRepository()
        self.entradas = 0
        self.commits = 0
        self.rollbacks = 0
        self.caida = caida
        self._committed = False

    async def __aenter__(self) -> Self:
        self.entradas += 1
        if self.caida:
            raise ConnectionRefusedError("PostgreSQL caído")
        self._committed = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self._committed:
            await self.rollback()

    async def commit(self) -> None:
        self.commits += 1
        self._committed = True

    async def rollback(self) -> None:
        self.rollbacks += 1
