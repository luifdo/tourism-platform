import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import get_settings
from app.infrastructure.cache.valkey_revocacion import (
    PREFIJO,
    PREFIJO_USUARIO,
    ValkeyRevocacionTokens,
    build_valkey_client,
)

pytestmark = pytest.mark.valkey

TTL_REVOCADO_DESDE = 15 * 60 + 10


@pytest.fixture
async def valkey() -> AsyncIterator[Redis]:
    client = build_valkey_client(get_settings().valkey_url)
    try:
        await asyncio.wait_for(client.ping(), timeout=3)
    except (RedisError, OSError, TimeoutError) as exc:
        await client.aclose()
        pytest.skip(f"Valkey no responde: {type(exc).__name__}")
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def nuevo_jti(valkey: Redis) -> AsyncIterator[Callable[[], str]]:
    """Genera jti de prueba y borra sus llaves al terminar."""
    creados: list[str] = []

    def crear() -> str:
        creados.append(f"prueba-{uuid.uuid4()}")
        return creados[-1]

    yield crear
    if creados:
        await valkey.delete(*(PREFIJO + jti for jti in creados))


@pytest.fixture
async def nuevo_usuario(valkey: Redis) -> AsyncIterator[Callable[[], uuid.UUID]]:
    """Genera ids de usuario de prueba y borra sus llaves revocado-desde al terminar."""
    creados: list[uuid.UUID] = []

    def crear() -> uuid.UUID:
        creados.append(uuid.uuid4())
        return creados[-1]

    yield crear
    if creados:
        await valkey.delete(*(PREFIJO_USUARIO + str(u) for u in creados))


@pytest.fixture
def revocacion(valkey: Redis) -> ValkeyRevocacionTokens:
    return ValkeyRevocacionTokens(
        valkey, reloj=lambda: datetime.now(UTC), ttl_revocado_desde=TTL_REVOCADO_DESDE
    )


async def test_revocar_y_consultar(
    revocacion: ValkeyRevocacionTokens,
    nuevo_jti: Callable[[], str],
    nuevo_usuario: Callable[[], uuid.UUID],
) -> None:
    jti, usuario_id, iat = nuevo_jti(), nuevo_usuario(), datetime.now(UTC)

    assert await revocacion.esta_revocado_token(jti, usuario_id, iat) is False
    await revocacion.revocar(jti, expira_en=datetime.now(UTC) + timedelta(seconds=120))

    assert await revocacion.esta_revocado_token(jti, usuario_id, iat) is True
    assert await revocacion.esta_revocado_token(nuevo_jti(), usuario_id, iat) is False


async def test_ttl_cercano_al_tiempo_restante_del_token(
    valkey: Redis, revocacion: ValkeyRevocacionTokens, nuevo_jti: Callable[[], str]
) -> None:
    jti = nuevo_jti()

    await revocacion.revocar(jti, expira_en=datetime.now(UTC) + timedelta(seconds=120))

    ttl = await valkey.ttl(PREFIJO + jti)
    assert 115 <= ttl <= 120


async def test_revocar_usuario_guarda_el_segundo_y_el_ttl(
    valkey: Redis, revocacion: ValkeyRevocacionTokens, nuevo_usuario: Callable[[], uuid.UUID]
) -> None:
    usuario_id = nuevo_usuario()
    desde = datetime.now(UTC).replace(microsecond=600_000)

    await revocacion.revocar_usuario(usuario_id, desde)

    llave = PREFIJO_USUARIO + str(usuario_id)
    assert await valkey.get(llave) == str(int(desde.timestamp())).encode()
    assert TTL_REVOCADO_DESDE - 5 <= await valkey.ttl(llave) <= TTL_REVOCADO_DESDE


async def test_esta_revocado_token_por_revocado_desde(
    revocacion: ValkeyRevocacionTokens,
    nuevo_jti: Callable[[], str],
    nuevo_usuario: Callable[[], uuid.UUID],
) -> None:
    usuario_id = nuevo_usuario()
    cambio = datetime.now(UTC).replace(microsecond=0)
    await revocacion.revocar_usuario(usuario_id, cambio.replace(microsecond=999_999))

    jti = nuevo_jti()
    antes = cambio - timedelta(seconds=1)
    despues = cambio + timedelta(seconds=1)
    assert await revocacion.esta_revocado_token(jti, usuario_id, antes) is True
    assert await revocacion.esta_revocado_token(jti, usuario_id, cambio) is True
    assert await revocacion.esta_revocado_token(jti, usuario_id, despues) is False
    # Otro usuario no se ve afectado.
    assert await revocacion.esta_revocado_token(jti, nuevo_usuario(), antes) is False
