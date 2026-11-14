from dataclasses import dataclass
from datetime import date

from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.tipo_servicio import TipoServicio


@dataclass(frozen=True, slots=True)
class FilaReporteDemanda:
    """Una fila del reporte UC38: un servicio en un día con actividad (reservas o intenciones).

    Las cantidades son personas, por fecha de la visita y estado actual de la reserva.
    """

    fecha: date
    zona: str | None  # nombre en español; sin zona, vacío
    servicio: str
    categoria: Categoria
    tipo: TipoServicio
    personas_solicitadas: int
    personas_confirmadas: int
    personas_finalizadas: int
    personas_canceladas: int  # incluye rechazadas
    capacidad_recomendada: int
    intenciones_visita: int

    @property
    def total_personas(self) -> int:
        """Las que vienen ese día: solicitadas + confirmadas + finalizadas (sin canceladas)."""
        return self.personas_solicitadas + self.personas_confirmadas + self.personas_finalizadas

    @property
    def indice(self) -> float:
        """Total de personas ÷ capacidad recomendada. Puede pasar de 1 (no es un tope)."""
        return round(self.total_personas / self.capacidad_recomendada, 4)
