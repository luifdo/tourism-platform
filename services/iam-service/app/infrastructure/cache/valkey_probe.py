import asyncio
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class ValkeyProbe:
    """Implementa CacheProbe con un PING a Valkey."""

    def __init__(self, client: Redis, timeout_seconds: float) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def ping(self) -> bool:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                await self._client.ping()
        except (RedisError, OSError, TimeoutError):
            logger.warning("Valkey no responde", exc_info=True)
            return False
        return True
