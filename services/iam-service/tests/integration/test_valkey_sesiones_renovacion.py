"""Script Lua de rotación contra un Valkey real (C-20, C-60).

Las llaves llevan TTL corto o se borran al terminar: no quedan en el Valkey de desarrollo.
"""

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.api.dependencies import get_sesiones_renovacion
from app.config import Settings, get_settings
from app.domain.value_objects.sesion import (
    RotacionInvalida,
    RotacionOk,
    RotacionReutilizada,
    RotacionRevocada,
)
from app.infrastructure.cache.valkey_revocacion import (
    PREFIJO_SESION,
    PREFIJO_USUARIO,
    ValkeyRevocacionTokens,
    build_valkey_client,
)
from app.infrastructure.cache.valkey_sesiones_renovacion import (
    PREFIJO_FAMILIA,
    PREFIJO_TOKEN,
    ValkeySesionesRenovacion,
)

pytestmark = pytest.mark.valkey

TTL_REFRESH = 300
TTL_SESION_REVOCADA = 120


def huella(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def ahora() -> datetime:
    return datetime.now(UTC)


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
def sesiones(valkey: Redis) -> ValkeySesionesRenovacion:
    return ValkeySesionesRenovacion(
        valkey, ahora, ttl_refresh=TTL_REFRESH, ttl_sesion_revocada=TTL_SESION_REVOCADA
    )


@pytest.fixture
def revocacion(valkey: Redis) -> ValkeyRevocacionTokens:
    return ValkeyRevocacionTokens(valkey, ahora, ttl_revocado_desde=TTL_REFRESH)


async def crear(
    sesiones: ValkeySesionesRenovacion, emitido_en: datetime | None = None
) -> tuple[str, str, uuid.UUID]:
    usuario_id = uuid.uuid4()
    familia = str(uuid.uuid4())
    creada = await sesiones.crear(usuario_id, familia, emitido_en or ahora())
    return creada.refresh_token, familia, usuario_id


async def campo(valkey: Redis, familia: str, nombre: str) -> str | None:
    valor = await valkey.hget(PREFIJO_FAMILIA + familia, nombre)
    return valor.decode() if valor is not None else None


async def test_crear_guarda_solo_el_hash_con_ttl(
    valkey: Redis, sesiones: ValkeySesionesRenovacion
) -> None:
    usuario_id = uuid.uuid4()
    familia = str(uuid.uuid4())
    emitido_en = ahora()

    creada = await sesiones.crear(usuario_id, familia, emitido_en)

    h = huella(creada.refresh_token)
    assert await valkey.exists(PREFIJO_TOKEN + creada.refresh_token) == 0
    assert await valkey.hgetall(PREFIJO_TOKEN + h) == {
        b"familia": familia.encode(),
        b"usuario_id": str(usuario_id).encode(),
        b"estado": b"vigente",
    }
    assert await valkey.hgetall(PREFIJO_FAMILIA + familia) == {
        b"usuario_id": str(usuario_id).encode(),
        b"actual": h.encode(),
        b"revocada": b"0",
        b"renovado_en": str(int(emitido_en.timestamp())).encode(),
    }
    for llave in (PREFIJO_TOKEN + h, PREFIJO_FAMILIA + familia):
        assert TTL_REFRESH - 5 <= await valkey.ttl(llave) <= TTL_REFRESH
    assert creada.expires_in == TTL_REFRESH
    assert creada.expira_en == emitido_en + timedelta(seconds=TTL_REFRESH)
    assert len(creada.refresh_token) <= 128
    assert creada.familia == familia


async def test_rotar_marca_el_viejo_y_conserva_su_ttl_y_renueva_la_familia(
    valkey: Redis, sesiones: ValkeySesionesRenovacion
) -> None:
    token, familia, usuario_id = await crear(sesiones)
    viejo = PREFIJO_TOKEN + huella(token)
    await valkey.expire(viejo, 100)
    await valkey.expire(PREFIJO_FAMILIA + familia, 100)

    resultado = await sesiones.rotar(token)

    assert isinstance(resultado, RotacionOk)
    assert (resultado.familia, resultado.usuario_id) == (familia, usuario_id)
    assert resultado.nuevo_token != token
    assert await valkey.hget(viejo, "estado") == b"rotado"
    # El rotado se conserva hasta que vence; no se le renueva el TTL.
    assert await valkey.ttl(viejo) <= 100
    nuevo = PREFIJO_TOKEN + huella(resultado.nuevo_token)
    assert await valkey.hget(nuevo, "estado") == b"vigente"
    assert TTL_REFRESH - 5 <= await valkey.ttl(nuevo) <= TTL_REFRESH
    assert TTL_REFRESH - 5 <= await valkey.ttl(PREFIJO_FAMILIA + familia) <= TTL_REFRESH
    assert await campo(valkey, familia, "actual") == huella(resultado.nuevo_token)
    assert await valkey.exists(PREFIJO_SESION + familia) == 0


async def test_cadena_de_rotaciones(sesiones: ValkeySesionesRenovacion) -> None:
    token, _, _ = await crear(sesiones)
    for _ in range(3):
        resultado = await sesiones.rotar(token)
        assert isinstance(resultado, RotacionOk)
        token = resultado.nuevo_token


async def test_token_desconocido_es_invalido_sin_crear_llaves(
    valkey: Redis, sesiones: ValkeySesionesRenovacion
) -> None:
    token = f"no-existe-{uuid.uuid4()}"

    assert isinstance(await sesiones.rotar(token), RotacionInvalida)
    assert await valkey.exists(PREFIJO_TOKEN + huella(token)) == 0


async def test_familia_vencida_es_invalido(
    valkey: Redis, sesiones: ValkeySesionesRenovacion
) -> None:
    token, familia, _ = await crear(sesiones)
    await valkey.delete(PREFIJO_FAMILIA + familia)

    assert isinstance(await sesiones.rotar(token), RotacionInvalida)


async def test_reutilizado_revoca_la_familia_y_escribe_la_sesion_revocada(
    valkey: Redis, sesiones: ValkeySesionesRenovacion
) -> None:
    token, familia, usuario_id = await crear(sesiones)
    primera = await sesiones.rotar(token)
    assert isinstance(primera, RotacionOk)

    resultado = await sesiones.rotar(token)

    assert isinstance(resultado, RotacionReutilizada)
    assert (resultado.familia, resultado.usuario_id) == (familia, usuario_id)
    assert await campo(valkey, familia, "revocada") == "1"
    assert await valkey.get(PREFIJO_SESION + familia) == b"1"
    assert await valkey.ttl(PREFIJO_SESION + familia) >= TTL_SESION_REVOCADA - 5
    assert await valkey.ttl(PREFIJO_SESION + familia) <= TTL_SESION_REVOCADA

    # El vigente cae, y repetir el rotado ya no es una detección nueva.
    assert isinstance(await sesiones.rotar(primera.nuevo_token), RotacionRevocada)
    assert isinstance(await sesiones.rotar(token), RotacionRevocada)


async def test_carrera_solo_uno_gana_y_la_familia_queda_revocada(
    valkey: Redis, sesiones: ValkeySesionesRenovacion
) -> None:
    token, familia, _ = await crear(sesiones)

    resultados = await asyncio.gather(sesiones.rotar(token), sesiones.rotar(token))

    assert sorted(type(r).__name__ for r in resultados) == ["RotacionOk", "RotacionReutilizada"]
    assert await campo(valkey, familia, "revocada") == "1"
    assert await valkey.exists(PREFIJO_SESION + familia) == 1
    ganador = next(r for r in resultados if isinstance(r, RotacionOk))
    assert isinstance(await sesiones.rotar(ganador.nuevo_token), RotacionRevocada)


async def test_carrera_amplia_exactamente_un_ok(
    sesiones: ValkeySesionesRenovacion,
) -> None:
    token, _, _ = await crear(sesiones)

    resultados = await asyncio.gather(*(sesiones.rotar(token) for _ in range(20)))

    assert sum(isinstance(r, RotacionOk) for r in resultados) == 1
    assert sum(isinstance(r, RotacionReutilizada) for r in resultados) == 1
    assert sum(isinstance(r, RotacionRevocada) for r in resultados) == 18


@pytest.mark.parametrize(
    ("desfase", "revocado"),
    [(1, True), (0, True), (-1, False)],
    ids=["marca_posterior", "mismo_segundo", "marca_anterior"],
)
async def test_regla_de_segundos_de_revocado_desde(
    valkey: Redis,
    sesiones: ValkeySesionesRenovacion,
    revocacion: ValkeyRevocacionTokens,
    desfase: int,
    revocado: bool,
) -> None:
    renovado_en = ahora().replace(microsecond=0)
    token, familia, usuario_id = await crear(sesiones, renovado_en)

    await revocacion.revocar_usuario(
        usuario_id, renovado_en.replace(microsecond=900_000) + timedelta(seconds=desfase)
    )

    resultado = await sesiones.rotar(token)
    if revocado:
        assert isinstance(resultado, RotacionRevocada)
        assert await campo(valkey, familia, "revocada") == "1"
        assert await valkey.exists(PREFIJO_SESION + familia) == 1
    else:
        assert isinstance(resultado, RotacionOk)
    assert await valkey.exists(PREFIJO_USUARIO + str(usuario_id)) == 1


async def test_token_rotado_de_cuenta_revocada_no_es_robo(
    sesiones: ValkeySesionesRenovacion, revocacion: ValkeyRevocacionTokens
) -> None:
    token, _, usuario_id = await crear(sesiones)
    assert isinstance(await sesiones.rotar(token), RotacionOk)

    await revocacion.revocar_usuario(usuario_id, ahora() + timedelta(seconds=5))

    assert isinstance(await sesiones.rotar(token), RotacionRevocada)


async def test_revocar_familia_impide_rotar(
    valkey: Redis, sesiones: ValkeySesionesRenovacion
) -> None:
    token, familia, _ = await crear(sesiones)
    ttl_antes = await valkey.ttl(PREFIJO_FAMILIA + familia)

    await sesiones.revocar_familia(familia)

    assert isinstance(await sesiones.rotar(token), RotacionRevocada)
    assert 0 < await valkey.ttl(PREFIJO_FAMILIA + familia) <= ttl_antes
    assert await valkey.get(PREFIJO_SESION + familia) == b"1"
    assert await valkey.ttl(PREFIJO_SESION + familia) >= TTL_SESION_REVOCADA - 5


async def test_revocar_familia_vencida_no_crea_una_llave_sin_ttl(
    valkey: Redis, sesiones: ValkeySesionesRenovacion
) -> None:
    familia = str(uuid.uuid4())

    await sesiones.revocar_familia(familia)

    assert await valkey.exists(PREFIJO_FAMILIA + familia) == 0
    # La marca sí se escribe, con TTL: cubre el access token aunque la familia se haya perdido.
    assert 0 < await valkey.ttl(PREFIJO_SESION + familia) <= TTL_SESION_REVOCADA


async def test_funciona_despues_de_vaciar_la_cache_de_scripts(
    valkey: Redis, sesiones: ValkeySesionesRenovacion
) -> None:
    token, familia, _ = await crear(sesiones)
    await valkey.script_flush()
    resultado = await sesiones.rotar(token)
    assert isinstance(resultado, RotacionOk)

    await valkey.script_flush()
    await sesiones.revocar_familia(familia)

    assert isinstance(await sesiones.rotar(resultado.nuevo_token), RotacionRevocada)


async def test_mget_con_tres_llaves_y_con_dos(
    valkey: Redis, sesiones: ValkeySesionesRenovacion, revocacion: ValkeyRevocacionTokens
) -> None:
    _, familia, usuario_id = await crear(sesiones)
    _, otra_familia, _ = await crear(sesiones)
    jti = f"prueba-{uuid.uuid4()}"
    iat = ahora()

    assert await revocacion.esta_revocado_token(jti, usuario_id, iat, familia) is False

    await sesiones.revocar_familia(familia)

    assert await revocacion.esta_revocado_token(jti, usuario_id, iat, familia) is True
    # Otra sesión del mismo usuario y un token sin sid no se ven afectados.
    assert await revocacion.esta_revocado_token(jti, usuario_id, iat, otra_familia) is False
    assert await revocacion.esta_revocado_token(jti, usuario_id, iat) is False


async def test_ttl_reales_de_la_configuracion(valkey: Redis) -> None:
    peticion = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(valkey=valkey)))
    sesiones = get_sesiones_renovacion(peticion, ahora, Settings())  # type: ignore[arg-type]
    usuario_id, familia = uuid.uuid4(), str(uuid.uuid4())
    creada = await sesiones.crear(usuario_id, familia, ahora())
    resultado = await sesiones.rotar(creada.refresh_token)
    assert isinstance(resultado, RotacionOk)
    siete_dias = 7 * 24 * 60 * 60
    llaves = [
        PREFIJO_TOKEN + huella(creada.refresh_token),
        PREFIJO_TOKEN + huella(resultado.nuevo_token),
        PREFIJO_FAMILIA + familia,
    ]
    try:
        for llave in llaves:
            assert siete_dias - 5 <= await valkey.ttl(llave) <= siete_dias
        await sesiones.revocar_familia(familia)
        assert 900 <= await valkey.ttl(PREFIJO_SESION + familia) <= 910
    finally:
        await valkey.delete(*llaves, PREFIJO_SESION + familia)
