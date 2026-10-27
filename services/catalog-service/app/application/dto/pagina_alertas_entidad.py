from dataclasses import dataclass
from datetime import datetime

from app.application.dto.alerta_editable import AlertaEditable


@dataclass(frozen=True, slots=True)
class PaginaAlertasEntidad:
    items: tuple[AlertaEditable, ...]
    pagina: int
    tamano: int
    total: int
    # Hora con la que se calculó el estado de cada alerta.
    ahora: datetime
