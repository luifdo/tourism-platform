import re
from dataclasses import dataclass

from app.domain.errors import DatoInvalido

_PATRON = re.compile(r"^[a-z0-9-]{2,40}$")


@dataclass(frozen=True, slots=True)
class CodigoZona:
    """Identificador legible de una zona (por ejemplo `minca`), estable para URLs y el chatbot."""

    valor: str

    def __post_init__(self) -> None:
        if not _PATRON.match(self.valor):
            raise DatoInvalido(campo="codigo", regla="patron", patron=_PATRON.pattern)

    def __str__(self) -> str:
        return self.valor
