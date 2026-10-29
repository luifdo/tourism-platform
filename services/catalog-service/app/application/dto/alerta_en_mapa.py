from dataclasses import dataclass
from typing import Any

from app.application.dto.alerta_vista import AlertaVista


@dataclass(frozen=True, slots=True)
class AlertaEnMapa:
    """Alerta con su geometría GeoJSON: el punto del servicio o el polígono de la zona."""

    alerta: AlertaVista
    geometria: dict[str, Any]
