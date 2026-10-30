from dataclasses import dataclass
from datetime import time
from typing import Any

from app.domain.value_objects.atributos import comun
from app.domain.value_objects.atributos.habitacion_ofrecida import HabitacionOfrecida
from app.domain.value_objects.atributos.valores import Amenidad


@dataclass(frozen=True, slots=True)
class BloqueAlojamiento:
    """Bloque B: hoteles, hostales, posadas, glamping y apartamentos."""

    check_in: time
    check_out: time
    habitaciones: tuple[HabitacionOfrecida, ...]
    amenidades: tuple[Amenidad, ...] = ()
    desayuno_incluido: bool = False

    def __post_init__(self) -> None:
        comun.no_vacio(self.habitaciones, "habitaciones")
        comun.sin_repetidos((h.tipo for h in self.habitaciones), "habitaciones")
        comun.sin_repetidos(self.amenidades, "amenidades")

    @property
    def total_habitaciones(self) -> int:
        return sum(h.cantidad for h in self.habitaciones)

    def a_json(self) -> dict[str, Any]:
        return comun.sin_nulos(
            {
                "check_in": comun.hora_a_json(self.check_in),
                "check_out": comun.hora_a_json(self.check_out),
                "habitaciones": [h.a_json() for h in self.habitaciones],
                "amenidades": comun.enums_a_json(self.amenidades),
                "desayuno_incluido": self.desayuno_incluido,
            }
        )

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "BloqueAlojamiento":
        return cls(
            check_in=time.fromisoformat(datos["check_in"]),
            check_out=time.fromisoformat(datos["check_out"]),
            habitaciones=tuple(HabitacionOfrecida.desde_json(h) for h in datos["habitaciones"]),
            amenidades=comun.enums_desde_json(Amenidad, datos.get("amenidades")),
            desayuno_incluido=datos.get("desayuno_incluido", False),
        )
