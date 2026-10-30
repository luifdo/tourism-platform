from enum import StrEnum


class OrdenResenas(StrEnum):
    """Orden de la lista pública; `mejores` y `peores` desempatan por la más reciente."""

    RECIENTES = "recientes"
    MEJORES = "mejores"
    PEORES = "peores"
