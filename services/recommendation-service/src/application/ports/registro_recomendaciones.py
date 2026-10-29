from collections.abc import Sequence
from typing import Protocol

from src.domain.recomendacion import RegistroRecomendacion


class RegistroRecomendaciones(Protocol):
    """Deja constancia de las recomendaciones entregadas (`recomendacion_log`)."""

    async def registrar(self, registros: Sequence[RegistroRecomendacion]) -> None: ...
