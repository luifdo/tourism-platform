from dataclasses import dataclass

from app.domain.ports.health import CacheProbe, DatabaseProbe


@dataclass(frozen=True)
class HealthReport:
    database: bool
    cache: bool

    @property
    def healthy(self) -> bool:
        return self.database and self.cache


class CheckHealth:
    """Estado de las dependencias para `/health` (Prometheus y Blackbox, RNF-01; C-32)."""

    def __init__(self, database: DatabaseProbe, cache: CacheProbe) -> None:
        self._database = database
        self._cache = cache

    async def execute(self) -> HealthReport:
        return HealthReport(database=await self._database.ping(), cache=await self._cache.ping())
