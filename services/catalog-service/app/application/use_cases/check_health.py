from dataclasses import dataclass

from app.domain.ports.health import DatabaseProbe


@dataclass(frozen=True)
class HealthReport:
    database: bool

    @property
    def healthy(self) -> bool:
        # Solo PostgreSQL decide: sin Valkey se busca sin caché y sin RabbitMQ el outbox
        # acumula los eventos, así que ninguno debe sacar la réplica del enrutamiento (ESC-01).
        return self.database


class CheckHealth:
    def __init__(self, database: DatabaseProbe) -> None:
        self._database = database

    async def execute(self) -> HealthReport:
        return HealthReport(database=await self._database.ping())
