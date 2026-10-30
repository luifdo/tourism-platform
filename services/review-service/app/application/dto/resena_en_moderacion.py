from dataclasses import dataclass

from app.domain.entities.reporte_resena import ReporteResena
from app.domain.entities.resena import Resena


@dataclass(frozen=True, slots=True)
class ResenaEnModeracion:
    """Una reseña de la cola del Administrador con sus reportes sin resolver."""

    resena: Resena
    reportes: list[ReporteResena]
