from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.atributos.cajeros_cercanos_datos import CajerosCercanosDatos
from app.api.schemas.atributos.credito_prestador_datos import CreditoPrestadorDatos
from app.domain.value_objects.atributos.bloque_pagos import BloquePagos
from app.domain.value_objects.atributos.valores import (
    MedioPago,
    RecomendacionDinero,
    SenalInternet,
)


class BloquePagosDatos(BaseModel):
    """Bloque H: dinero y pagos en el lugar (señal, medios, crédito y cajeros)."""

    model_config = ConfigDict(extra="forbid")

    senal_internet: SenalInternet
    medios_pago: list[MedioPago]
    recomendacion_dinero: RecomendacionDinero
    credito: CreditoPrestadorDatos = Field(default_factory=CreditoPrestadorDatos)
    cajeros: CajerosCercanosDatos | None = None

    def a_dominio(self) -> BloquePagos:
        return BloquePagos(
            senal_internet=self.senal_internet,
            medios_pago=tuple(self.medios_pago),
            recomendacion_dinero=self.recomendacion_dinero,
            credito=self.credito.a_dominio(),
            cajeros=self.cajeros.a_dominio() if self.cajeros else None,
        )

    @classmethod
    def desde(cls, bloque: BloquePagos) -> "BloquePagosDatos":
        return cls(
            senal_internet=bloque.senal_internet,
            medios_pago=list(bloque.medios_pago),
            recomendacion_dinero=bloque.recomendacion_dinero,
            credito=CreditoPrestadorDatos.desde(bloque.credito),
            cajeros=CajerosCercanosDatos.desde(bloque.cajeros) if bloque.cajeros else None,
        )
