from dataclasses import dataclass
from typing import Any

from app.domain.errors import DatoInvalido
from app.domain.value_objects.atributos import comun
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class CajerosCercanos:
    """Si hay cajeros en la zona de la actividad y, si no, dónde está el más cercano."""

    hay_cerca: bool
    referencia: TextoTraducido | None = None
    distancia_km: float | None = None

    def __post_init__(self) -> None:
        if self.distancia_km is not None and not 0 <= self.distancia_km <= 200:
            raise DatoInvalido(campo="distancia_km", regla="rango", minimo=0, maximo=200)

    def a_json(self) -> dict[str, Any]:
        return comun.sin_nulos(
            {
                "hay_cerca": self.hay_cerca,
                "referencia": comun.texto_a_json(self.referencia),
                "distancia_km": self.distancia_km,
            }
        )

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "CajerosCercanos":
        return cls(
            hay_cerca=datos["hay_cerca"],
            referencia=comun.texto_desde_json(datos.get("referencia")),
            distancia_km=datos.get("distancia_km"),
        )
