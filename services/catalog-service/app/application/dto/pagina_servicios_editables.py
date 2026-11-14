from dataclasses import dataclass

from app.application.dto.servicio_editable import ServicioEditable


@dataclass(frozen=True, slots=True)
class PaginaServiciosEditables:
    items: tuple[ServicioEditable, ...]
    pagina: int
    tamano: int
    total: int
