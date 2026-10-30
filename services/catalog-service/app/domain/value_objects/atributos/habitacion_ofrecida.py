from dataclasses import dataclass
from typing import Any

from app.domain.value_objects.atributos import comun
from app.domain.value_objects.atributos.valores import TipoHabitacion


@dataclass(frozen=True, slots=True)
class HabitacionOfrecida:
    """Un tipo de habitación del alojamiento: cuántas hay y cuántas personas caben en cada una."""

    tipo: TipoHabitacion
    capacidad_personas: int
    cantidad: int = 1

    def __post_init__(self) -> None:
        comun.en_rango(self.capacidad_personas, "capacidad_personas", 1, 50)
        comun.en_rango(self.cantidad, "cantidad", 1, 500)

    def a_json(self) -> dict[str, Any]:
        return {
            "tipo": self.tipo.value,
            "capacidad_personas": self.capacidad_personas,
            "cantidad": self.cantidad,
        }

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "HabitacionOfrecida":
        return cls(
            tipo=TipoHabitacion(datos["tipo"]),
            capacidad_personas=datos["capacidad_personas"],
            cantidad=datos.get("cantidad", 1),
        )
