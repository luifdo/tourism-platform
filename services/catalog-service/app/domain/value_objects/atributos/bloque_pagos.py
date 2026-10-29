from dataclasses import dataclass, field
from typing import Any

from app.domain.errors import DatoInvalido
from app.domain.value_objects.atributos import comun
from app.domain.value_objects.atributos.cajeros_cercanos import CajerosCercanos
from app.domain.value_objects.atributos.credito_prestador import CreditoPrestador
from app.domain.value_objects.atributos.valores import (
    MedioPago,
    RecomendacionDinero,
    SenalInternet,
)


@dataclass(frozen=True, slots=True)
class BloquePagos:
    """Bloque H: cómo pagar en el lugar cuando puede no haber señal ni cajeros.

    Lo admiten todos los tipos; la PWA lo sugiere en experiencias, entradas y transporte.
    """

    senal_internet: SenalInternet
    medios_pago: tuple[MedioPago, ...]
    recomendacion_dinero: RecomendacionDinero
    credito: CreditoPrestador = field(default_factory=CreditoPrestador)
    cajeros: CajerosCercanos | None = None

    def __post_init__(self) -> None:
        comun.no_vacio(self.medios_pago, "medios_pago")
        comun.sin_repetidos(self.medios_pago, "medios_pago")
        acepta_digital = any(m.digital for m in self.medios_pago)
        if self.recomendacion_dinero is RecomendacionDinero.DIGITAL and not acepta_digital:
            raise DatoInvalido(campo="recomendacion_dinero", regla="recomendacion_sin_medio")
        if (
            self.recomendacion_dinero is RecomendacionDinero.EFECTIVO
            and MedioPago.EFECTIVO not in self.medios_pago
        ):
            raise DatoInvalido(campo="recomendacion_dinero", regla="recomendacion_sin_medio")

    @property
    def acepta_pago_digital(self) -> bool:
        return any(m.digital for m in self.medios_pago)

    def a_json(self) -> dict[str, Any]:
        # `acepta_pago_digital` se guarda calculado para filtrarlo con el índice GIN.
        return comun.sin_nulos(
            {
                "senal_internet": self.senal_internet.value,
                "medios_pago": comun.enums_a_json(self.medios_pago),
                "acepta_pago_digital": self.acepta_pago_digital,
                "recomendacion_dinero": self.recomendacion_dinero.value,
                "credito": self.credito.a_json(),
                "cajeros": self.cajeros.a_json() if self.cajeros else None,
            }
        )

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "BloquePagos":
        cajeros = datos.get("cajeros")
        return cls(
            senal_internet=SenalInternet(datos["senal_internet"]),
            medios_pago=comun.enums_desde_json(MedioPago, datos["medios_pago"]),
            recomendacion_dinero=RecomendacionDinero(datos["recomendacion_dinero"]),
            credito=CreditoPrestador.desde_json(datos.get("credito", {})),
            cajeros=CajerosCercanos.desde_json(cajeros) if cajeros else None,
        )
