"""Puerto de persistencia `AlertaRepository` (adaptador en persistence/repositorios)."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.entities.alerta_oficial import AlertaOficial


class AlertaRepository(Protocol):
    async def obtener(self, alerta_id: UUID) -> AlertaOficial | None: ...

    async def contar_vigentes_de_zona(self, zona_id: UUID, ahora: datetime) -> int: ...

    async def guardar(self, alerta: AlertaOficial) -> None: ...
