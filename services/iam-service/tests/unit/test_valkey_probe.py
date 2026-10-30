from redis.exceptions import ConnectionError as RedisConnectionError

from app.infrastructure.cache.valkey_probe import ValkeyProbe


class ClienteFalso:
    def __init__(self, caido: bool) -> None:
        self.caido = caido

    async def ping(self) -> bool:
        if self.caido:
            raise RedisConnectionError("Valkey caído")
        return True


async def test_ping_ok() -> None:
    assert await ValkeyProbe(ClienteFalso(caido=False), 1.0).ping() is True  # type: ignore[arg-type]


async def test_valkey_caido_es_false() -> None:
    assert await ValkeyProbe(ClienteFalso(caido=True), 1.0).ping() is False  # type: ignore[arg-type]
