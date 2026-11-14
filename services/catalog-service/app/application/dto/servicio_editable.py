from dataclasses import dataclass

from app.application.dto.zona_resumen import ZonaResumen
from app.domain.entities.atractivo_servicio import AtractivoServicio


@dataclass(frozen=True, slots=True)
class ServicioEditable:
    """Servicio como lo ve su dueño: con ambos idiomas, inactivo incluido y su versión."""

    servicio: AtractivoServicio
    zona: ZonaResumen | None
