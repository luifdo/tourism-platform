from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.value_objects.atributos import comun
from app.domain.value_objects.atributos.valores import TipoVisitante
from app.domain.value_objects.tarifa import Tarifa


@dataclass(frozen=True, slots=True)
class TarifaVisitante:
    """Precio de entrada para un tipo de visitante (p. ej. nacional o extranjero)."""

    tipo_visitante: TipoVisitante
    valor: Tarifa

    def a_json(self) -> dict[str, Any]:
        return {
            "tipo_visitante": self.tipo_visitante.value,
            "valor": comun.pesos_a_json(self.valor.valor),
        }

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "TarifaVisitante":
        return cls(
            tipo_visitante=TipoVisitante(datos["tipo_visitante"]),
            valor=Tarifa(Decimal(datos["valor"])),
        )
