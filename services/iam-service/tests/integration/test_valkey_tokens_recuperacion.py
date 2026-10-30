"""Tokens de recuperación y enfriamiento contra Valkey (C-28)."""

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import get_settings
from app.domain.exceptions import ServicioNoDisponibleError
from app.infrastructure.cache.valkey_revocacion import build_valkey_client
from app.infrastructure.cache.valkey_tokens_recuperacion import (
    PREFIJO_ESPERA,
    PREFIJO_TOKEN,
    PREFIJO_VIGENTE,
    ValkeyTokensRecuperacion,
)

pytestmark = pytest.mark.valkey


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
async def usuario_id(valkey: Redis) -> AsyncIterator[uuid.UUID]:
    """Usuario de prueba; borra sus llaves al terminar."""
    nuevo = uuid.uuid4()
    yield nuevo
    vigente = await valkey.get(PREFIJO_VIGENTE + str(nuevo))
    llaves = [PREFIJO_VIGENTE + str(nuevo), PREFIJO_ESPERA + str(nuevo)]
    if vigente is not None:
        llaves.append(PREFIJO_TOKEN + vigente.decode())
    await valkey.delete(*llaves)


@pytest.fixture
def tokens(valkey: Redis) -> ValkeyTokensRecuperacion:
    return ValkeyTokensRecuperacion(valkey)


def llave(token: str) -> str:
    return "iam:reset:" + hashlib.sha256(token.encode()).hexdigest()


async def test_guarda_el_sha256_con_ttl_de_30_minutos_y_nunca_el_token(
    valkey: Redis, tokens: ValkeyTokensRecuperacion, usuario_id: uuid.UUID
) -> None:
    token = f"secreto-{uuid.uuid4()}"

    await tokens.guardar(token, usuario_id)

    assert await valkey.get(llave(token)) == str(usuario_id).encode()
    assert 30 * 60 - 5 <= await valkey.ttl(llave(token)) <= 30 * 60
    assert await valkey.get(f"iam:reset:{token}") is None
    assert token.encode() not in (await valkey.get(PREFIJO_VIGENTE + str(usuario_id)))


async def test_consumir_es_de_un_solo_uso(
    tokens: ValkeyTokensRecuperacion, usuario_id: uuid.UUID
) -> None:
    token = f"secreto-{uuid.uuid4()}"
    await tokens.guardar(token, usuario_id)

    assert await tokens.consumir(token) == usuario_id
    assert await tokens.consumir(token) is None


async def test_dos_peticiones_simultaneas_solo_una_lo_consume(
    tokens: ValkeyTokensRecuperacion, usuario_id: uuid.UUID
) -> None:
    token = f"secreto-{uuid.uuid4()}"
    await tokens.guardar(token, usuario_id)

    resultados = await asyncio.gather(*(tokens.consumir(token) for _ in range(5)))

    assert sorted(r is not None for r in resultados) == [False, False, False, False, True]


async def test_token_desconocido_o_vencido_es_none(
    valkey: Redis, tokens: ValkeyTokensRecuperacion, usuario_id: uuid.UUID
) -> None:
    token = f"secreto-{uuid.uuid4()}"
    await tokens.guardar(token, usuario_id)
    await valkey.pexpire(llave(token), 1)
    await asyncio.sleep(0.05)

    assert await tokens.consumir(token) is None
    assert await tokens.consumir("no-existe") is None


async def test_un_token_nuevo_invalida_el_anterior(
    tokens: ValkeyTokensRecuperacion, usuario_id: uuid.UUID
) -> None:
    viejo, nuevo = f"viejo-{uuid.uuid4()}", f"nuevo-{uuid.uuid4()}"
    await tokens.guardar(viejo, usuario_id)

    await tokens.guardar(nuevo, usuario_id)

    assert await tokens.consumir(viejo) is None
    assert await tokens.consumir(nuevo) == usuario_id


async def test_enfriamiento_de_60_segundos_atomico(
    valkey: Redis, tokens: ValkeyTokensRecuperacion, usuario_id: uuid.UUID
) -> None:
    resultados = await asyncio.gather(*(tokens.reservar_envio(usuario_id) for _ in range(5)))

    assert sorted(resultados) == [False, False, False, False, True]
    assert 55 <= await valkey.ttl(f"iam:reset-espera:{usuario_id}") <= 60


async def test_descartar_borra_el_token_y_la_espera(
    tokens: ValkeyTokensRecuperacion, usuario_id: uuid.UUID
) -> None:
    token = f"secreto-{uuid.uuid4()}"
    await tokens.reservar_envio(usuario_id)
    await tokens.guardar(token, usuario_id)

    await tokens.descartar(usuario_id)

    assert await tokens.consumir(token) is None
    assert await tokens.reservar_envio(usuario_id) is True


async def test_valkey_caido_es_servicio_no_disponible() -> None:
    caido = ValkeyTokensRecuperacion(build_valkey_client("redis://127.0.0.1:1/0"))
    usuario = uuid.uuid4()

    for llamada in (
        caido.reservar_envio(usuario),
        caido.guardar("t", usuario),
        caido.consumir("t"),
        caido.descartar(usuario),
    ):
        with pytest.raises(ServicioNoDisponibleError):
            await llamada
