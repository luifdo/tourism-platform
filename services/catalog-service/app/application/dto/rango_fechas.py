from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.errors import DatoInvalido

DIAS_MAXIMOS = 366


@dataclass(frozen=True, slots=True)
class RangoFechas:
    """Rango de días de la analítica (`desde` y `hasta` incluidos), de hasta 366 días."""

    desde: date
    hasta: date

    def __post_init__(self) -> None:
        if self.desde > self.hasta:
            raise DatoInvalido(campo="desde", regla="mayor_que", otro="hasta")
        if self.hasta - self.desde > timedelta(days=DIAS_MAXIMOS):
            raise DatoInvalido(campo="hasta", regla="plazo_maximo", dias=DIAS_MAXIMOS)

    @property
    def dias(self) -> int:
        return (self.hasta - self.desde).days + 1
