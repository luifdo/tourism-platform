from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

# En Windows la base de zonas horarias la aporta el paquete tzdata.
ZONA_NEGOCIO = ZoneInfo("America/Bogota")


class RelojSistema:
    """Implementa Reloj con la hora del sistema."""

    def ahora(self) -> datetime:
        return datetime.now(UTC)

    def hoy(self) -> date:
        return datetime.now(ZONA_NEGOCIO).date()
