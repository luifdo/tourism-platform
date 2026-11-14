from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.dto.alerta_vista import AlertaVista
from app.application.dto.estado_alerta import EstadoAlerta
from app.application.dto.pagina_alertas_entidad import PaginaAlertasEntidad


class ConsultaAlertas(Protocol):
    async def vigentes(
        self, ahora: datetime, zona: str | None = None, servicio_id: UUID | None = None
    ) -> list[AlertaVista]:
        """Alertas activas y no expiradas, de mayor a menor nivel.

        Con `servicio_id` incluye también las alertas de la zona del servicio, porque afectan
        a quien lo visita.
        """
        ...

    async def de_entidad(
        self, ahora: datetime, estado: EstadoAlerta | None, pagina: int, tamano: int
    ) -> PaginaAlertasEntidad:
        """Panel de la Entidad: todas las alertas (o las de un estado), de la más reciente a
        la más antigua, sin bloquear filas."""
        ...
