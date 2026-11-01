"""Fallos de Valkey y TTL configurados. El script Lua se prueba en integración."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError, ResponseError

from app.api.dependencies import get_revocacion, get_sesiones_renovacion
from app.config import Settings
from app.domain.exceptions import ServicioNoDisponibleError
from app.infrastructure.cache.valkey_sesiones_renovacion import ValkeySesionesRenovacion
from tests.fakes import FakeRedisClient

AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)


class ClienteQueFalla:
    def __init__(self, error: RedisError) -> None:
        self.error = error

    def register_script(self, _: str) -> Any:
        async def script(**_: Any) -> None:
            raise self.error

        return script

    def pipeline(self, **_: Any) -> Any:
        raise self.error


def sesiones(error: RedisError) -> ValkeySesionesRenovacion:
    return ValkeySesionesRenovacion(
        ClienteQueFalla(error),  # type: ignore[arg-type]
        reloj=lambda: AHORA,
        ttl_refresh=60,
        ttl_sesion_revocada=60,
    )


@pytest.mark.parametrize(
    "error",
    [RedisConnectionError("caído"), ResponseError("OOM command not allowed")],
    ids=["conexion", "respuesta"],
)
async def test_falla_cerrado_con_cualquier_error_de_valkey(error: RedisError) -> None:
    caso = sesiones(error)

    with pytest.raises(ServicioNoDisponibleError):
        await caso.crear(uuid.uuid4(), "f", AHORA)
    with pytest.raises(ServicioNoDisponibleError):
        await caso.rotar("t")
    with pytest.raises(ServicioNoDisponibleError):
        await caso.revocar_familia("f")


def peticion(cliente: object) -> Any:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(valkey=cliente)))


async def test_revocado_desde_vive_siete_dias_mas_el_margen() -> None:
    redis = FakeRedisClient()
    usuario_id = uuid.uuid4()
    revocacion = get_revocacion(peticion(redis), lambda: AHORA, Settings())

    await revocacion.revocar_usuario(usuario_id, AHORA)

    assert redis.ttls == {f"iam:revocado-desde:{usuario_id}": 7 * 24 * 60 * 60 + 10}


def test_ttl_de_las_sesiones_salen_de_la_configuracion() -> None:
    caso = get_sesiones_renovacion(peticion(object()), lambda: AHORA, Settings())

    assert isinstance(caso, ValkeySesionesRenovacion)
    assert caso._ttl_refresh == 7 * 24 * 60 * 60
    assert caso._ttl_sesion_revocada == 15 * 60 + 10
