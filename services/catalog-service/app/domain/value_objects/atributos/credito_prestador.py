from dataclasses import dataclass
from typing import Any

from app.domain.errors import DatoInvalido
from app.domain.value_objects.atributos import comun
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class CreditoPrestador:
    """El prestador cubre el gasto si el turista no tiene con qué pagar en el lugar, y el
    turista le paga después (al recuperar señal o pasar por un cajero).

    Es un acuerdo entre ellos: la plataforma lo informa, no lo cobra ni lo garantiza.
    """

    ofrece: bool = False
    plazo_dias: int | None = None
    condiciones: TextoTraducido | None = None

    def __post_init__(self) -> None:
        if not self.ofrece and (self.plazo_dias is not None or self.condiciones is not None):
            raise DatoInvalido(campo="credito", regla="requiere", requiere="credito.ofrece")
        comun.en_rango(self.plazo_dias, "plazo_dias", 1, 90)

    def a_json(self) -> dict[str, Any]:
        return comun.sin_nulos(
            {
                "ofrece": self.ofrece,
                "plazo_dias": self.plazo_dias,
                "condiciones": comun.texto_a_json(self.condiciones),
            }
        )

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "CreditoPrestador":
        return cls(
            ofrece=datos.get("ofrece", False),
            plazo_dias=datos.get("plazo_dias"),
            condiciones=comun.texto_desde_json(datos.get("condiciones")),
        )
