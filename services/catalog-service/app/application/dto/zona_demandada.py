from dataclasses import dataclass

from app.application.dto.zona_resumen import ZonaResumen


@dataclass(frozen=True, slots=True)
class ZonaDemandada:
    """Personas que vienen a la zona en el rango (reservas no canceladas) e intenciones."""

    zona: ZonaResumen
    personas: int
    intenciones_visita: int
