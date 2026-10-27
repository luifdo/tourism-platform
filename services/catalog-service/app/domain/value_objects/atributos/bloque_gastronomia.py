from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.value_objects.atributos import comun
from app.domain.value_objects.atributos.valores import OpcionDietaria, TipoCocina
from app.domain.value_objects.tarifa import Tarifa


@dataclass(frozen=True, slots=True)
class BloqueGastronomia:
    """Bloque D: restaurantes, cafés y bares (y experiencias gastronómicas, como opcional)."""

    tipos_cocina: tuple[TipoCocina, ...]
    opciones_dietarias: tuple[OpcionDietaria, ...] = ()
    precio_min_persona: Tarifa | None = None
    precio_max_persona: Tarifa | None = None
    requiere_reserva: bool = False
    puestos: int | None = None
    domicilio: bool = False

    def __post_init__(self) -> None:
        comun.no_vacio(self.tipos_cocina, "tipos_cocina")
        comun.sin_repetidos(self.tipos_cocina, "tipos_cocina")
        comun.sin_repetidos(self.opciones_dietarias, "opciones_dietarias")
        comun.no_mayor(
            self.precio_min_persona.valor if self.precio_min_persona else None,
            self.precio_max_persona.valor if self.precio_max_persona else None,
            "precio_min_persona",
            "precio_max_persona",
        )
        comun.en_rango(self.puestos, "puestos", 1, 5000)

    def a_json(self) -> dict[str, Any]:
        return comun.sin_nulos(
            {
                "tipos_cocina": comun.enums_a_json(self.tipos_cocina),
                "opciones_dietarias": comun.enums_a_json(self.opciones_dietarias),
                "precio_min_persona": _pesos(self.precio_min_persona),
                "precio_max_persona": _pesos(self.precio_max_persona),
                "requiere_reserva": self.requiere_reserva,
                "puestos": self.puestos,
                "domicilio": self.domicilio,
            }
        )

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "BloqueGastronomia":
        return cls(
            tipos_cocina=comun.enums_desde_json(TipoCocina, datos["tipos_cocina"]),
            opciones_dietarias=comun.enums_desde_json(
                OpcionDietaria, datos.get("opciones_dietarias")
            ),
            precio_min_persona=_tarifa(datos.get("precio_min_persona")),
            precio_max_persona=_tarifa(datos.get("precio_max_persona")),
            requiere_reserva=datos.get("requiere_reserva", False),
            puestos=datos.get("puestos"),
            domicilio=datos.get("domicilio", False),
        )


def _pesos(tarifa: Tarifa | None) -> str | None:
    return comun.pesos_a_json(tarifa.valor if tarifa else None)


def _tarifa(valor: str | None) -> Tarifa | None:
    return Tarifa(Decimal(valor)) if valor is not None else None
