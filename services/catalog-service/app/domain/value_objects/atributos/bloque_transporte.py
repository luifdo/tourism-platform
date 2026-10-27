from dataclasses import dataclass
from datetime import time
from typing import Any

from app.domain.value_objects.atributos import comun
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class BloqueTransporte:
    """Bloque G: lanchas (p. ej. Taganga → Playa Cristal) y traslados terrestres."""

    origen: TextoTraducido
    destino: TextoTraducido
    duracion_minutos: int
    capacidad_vehiculo: int
    horarios_salida: tuple[time, ...] = ()
    incluye_chaleco_salvavidas: bool | None = None

    def __post_init__(self) -> None:
        comun.en_rango(self.duracion_minutos, "duracion_minutos", 1, 24 * 60)
        comun.en_rango(self.capacidad_vehiculo, "capacidad_vehiculo", 1, 500)
        comun.sin_repetidos(self.horarios_salida, "horarios_salida")
        object.__setattr__(self, "horarios_salida", tuple(sorted(self.horarios_salida)))

    def a_json(self) -> dict[str, Any]:
        return comun.sin_nulos(
            {
                "origen": comun.texto_a_json(self.origen),
                "destino": comun.texto_a_json(self.destino),
                "duracion_minutos": self.duracion_minutos,
                "capacidad_vehiculo": self.capacidad_vehiculo,
                "horarios_salida": [comun.hora_a_json(h) for h in self.horarios_salida],
                "incluye_chaleco_salvavidas": self.incluye_chaleco_salvavidas,
            }
        )

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "BloqueTransporte":
        return cls(
            origen=TextoTraducido(**datos["origen"]),
            destino=TextoTraducido(**datos["destino"]),
            duracion_minutos=datos["duracion_minutos"],
            capacidad_vehiculo=datos["capacidad_vehiculo"],
            horarios_salida=tuple(time.fromisoformat(h) for h in datos.get("horarios_salida", ())),
            incluye_chaleco_salvavidas=datos.get("incluye_chaleco_salvavidas"),
        )
