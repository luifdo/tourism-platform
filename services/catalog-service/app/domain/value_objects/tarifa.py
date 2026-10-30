from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.domain.errors import DatoInvalido

_MAXIMO = Decimal("9999999999.99")  # Numeric(12, 2) en la base de datos


@dataclass(frozen=True, slots=True)
class Tarifa:
    """Tarifa en pesos colombianos (COP), con dos decimales."""

    valor: Decimal

    def __post_init__(self) -> None:
        try:
            valor = Decimal(self.valor).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise DatoInvalido(campo="tarifa_base", regla="numero") from exc
        if valor < 0 or valor > _MAXIMO:
            raise DatoInvalido(campo="tarifa_base", regla="rango", minimo=0, maximo=str(_MAXIMO))
        object.__setattr__(self, "valor", valor)
