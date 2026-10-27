from dataclasses import dataclass

from app.application.dto.zona_en_mapa import ZonaEnMapa
from app.domain.services.calculadora_saturacion import ResultadoSaturacion


@dataclass(frozen=True, slots=True)
class ZonaConSaturacion:
    """Polígono de una zona para el mapa de calor; sin servicios, `saturacion` es None."""

    zona: ZonaEnMapa
    saturacion: ResultadoSaturacion | None
