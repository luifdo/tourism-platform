from dataclasses import dataclass

from app.application.dto.resena_en_moderacion import ResenaEnModeracion


@dataclass(frozen=True, slots=True)
class PaginaModeracion:
    """Una página de la cola de moderación y el total de reseñas que esperan decisión."""

    items: list[ResenaEnModeracion]
    pagina: int
    tamano: int
    total: int
