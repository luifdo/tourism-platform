from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SubidaImagen:
    """URL firmada para un PUT directo al almacén y la URL pública que irá en el servicio."""

    subida_url: str
    url_publica: str
    expira_en: datetime
