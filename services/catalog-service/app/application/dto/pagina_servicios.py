from dataclasses import dataclass

from app.application.dto.servicio_resumen import ServicioResumen


@dataclass(frozen=True, slots=True)
class PaginaServicios:
    items: tuple[ServicioResumen, ...]
    pagina: int
    tamano: int
    total: int
