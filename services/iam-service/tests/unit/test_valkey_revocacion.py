import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.exceptions import ServicioNoDisponibleError
from app.infrastructure.cache.valkey_revocacion import ValkeyRevocacionTokens
from tests.fakes import FakeRedisClient

AHORA = datetime(2026, 10, 23, 15, 0, 30, tzinfo=UTC)
USUARIO_ID = uuid.uuid4()
TTL = 15 * 60 + 10


def revocacion(redis: FakeRedisClient) -> ValkeyRevocacionTokens:
    return ValkeyRevocacionTokens(
        redis,  # type: ignore[arg-type]
        reloj=lambda: AHORA,
        ttl_revocado_desde=TTL,
    )


async def test_revocar_usuario_guarda_segundos_enteros_con_ttl() -> None:
    redis = FakeRedisClient()

    await revocacion(redis).revocar_usuario(USUARIO_ID, desde=AHORA.replace(microsecond=750_000))

    llave = f"iam:revocado-desde:{USUARIO_ID}"
    assert redis.valores == {llave: str(int(AHORA.timestamp()))}
    assert redis.ttls == {llave: TTL}


@pytest.mark.parametrize(
    ("iat", "revocado"),
    [
        (AHORA - timedelta(seconds=1), True),
        # Mismo segundo de la revocación (iat va en segundos): también queda revocado.
        (AHORA, True),
        (AHORA + timedelta(seconds=1), False),
    ],
    ids=["antes", "mismo_segundo", "despues"],
)
async def test_revocado_desde(iat: datetime, revocado: bool) -> None:
    redis = FakeRedisClient()
    rev = revocacion(redis)
    await rev.revocar_usuario(USUARIO_ID, desde=AHORA.replace(microsecond=999_999))

    assert await rev.esta_revocado_token("jti-nuevo", USUARIO_ID, iat) is revocado
    # Las dos llaves se consultan en una sola ida a Valkey.
    assert redis.llamadas_mget == 1


async def test_revocado_por_jti() -> None:
    redis = FakeRedisClient()
    rev = revocacion(redis)
    await rev.revocar("jti-1", expira_en=AHORA + timedelta(minutes=5))

    assert await rev.esta_revocado_token("jti-1", USUARIO_ID, AHORA) is True
    assert await rev.esta_revocado_token("jti-2", USUARIO_ID, AHORA) is False


async def test_revocacion_de_otro_usuario_no_afecta() -> None:
    redis = FakeRedisClient()
    rev = revocacion(redis)
    await rev.revocar_usuario(uuid.uuid4(), desde=AHORA)

    assert await rev.esta_revocado_token("jti", USUARIO_ID, AHORA) is False


async def test_falla_cerrado_si_valkey_no_responde() -> None:
    rev = revocacion(FakeRedisClient(caido=True))

    with pytest.raises(ServicioNoDisponibleError):
        await rev.revocar_usuario(USUARIO_ID, desde=AHORA)
    with pytest.raises(ServicioNoDisponibleError):
        await rev.esta_revocado_token("jti", USUARIO_ID, AHORA)
