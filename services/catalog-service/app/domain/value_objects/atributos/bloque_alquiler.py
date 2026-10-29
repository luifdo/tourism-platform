from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.value_objects.atributos import comun
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class BloqueAlquiler:
    """Bloque F: alquiler de equipo (carpas, sillas, snorkel, kayaks). El tiempo de alquiler
    lo da `unidad_tarifa` (por hora, por día...)."""

    equipos: TextoTraducido
    deposito: Tarifa | None = None
    requiere_documento: bool = False

    def a_json(self) -> dict[str, Any]:
        return comun.sin_nulos(
            {
                "equipos": comun.texto_a_json(self.equipos),
                "deposito": comun.pesos_a_json(self.deposito.valor if self.deposito else None),
                "requiere_documento": self.requiere_documento,
            }
        )

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "BloqueAlquiler":
        deposito = datos.get("deposito")
        return cls(
            equipos=TextoTraducido(**datos["equipos"]),
            deposito=Tarifa(Decimal(deposito)) if deposito is not None else None,
            requiere_documento=datos.get("requiere_documento", False),
        )
