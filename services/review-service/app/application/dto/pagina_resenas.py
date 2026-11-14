from dataclasses import dataclass

from app.domain.entities.resena import Resena


@dataclass(frozen=True, slots=True)
class PaginaResenas:
    """Una página de reseñas y el total de las que cumplen el filtro."""

    items: list[Resena]
    pagina: int
    tamano: int
    total: int
