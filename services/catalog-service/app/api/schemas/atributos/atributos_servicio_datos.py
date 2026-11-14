from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.atributos.bloque_alojamiento_datos import BloqueAlojamientoDatos
from app.api.schemas.atributos.bloque_alquiler_datos import BloqueAlquilerDatos
from app.api.schemas.atributos.bloque_comunes_datos import BloqueComunesDatos
from app.api.schemas.atributos.bloque_entrada_datos import BloqueEntradaDatos
from app.api.schemas.atributos.bloque_experiencia_datos import BloqueExperienciaDatos
from app.api.schemas.atributos.bloque_gastronomia_datos import BloqueGastronomiaDatos
from app.api.schemas.atributos.bloque_pagos_datos import BloquePagosDatos
from app.api.schemas.atributos.bloque_transporte_datos import BloqueTransporteDatos
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio


class AtributosServicioDatos(BaseModel):
    """Bloques de atributos del servicio. Qué bloques admite cada tipo lo valida el dominio."""

    model_config = ConfigDict(extra="forbid")

    comunes: BloqueComunesDatos = Field(default_factory=BloqueComunesDatos)
    alojamiento: BloqueAlojamientoDatos | None = None
    experiencia: BloqueExperienciaDatos | None = None
    gastronomia: BloqueGastronomiaDatos | None = None
    entrada: BloqueEntradaDatos | None = None
    alquiler: BloqueAlquilerDatos | None = None
    transporte: BloqueTransporteDatos | None = None
    pagos: BloquePagosDatos | None = None

    def a_dominio(self) -> AtributosServicio:
        return AtributosServicio(
            comunes=self.comunes.a_dominio(),
            alojamiento=self.alojamiento.a_dominio() if self.alojamiento else None,
            experiencia=self.experiencia.a_dominio() if self.experiencia else None,
            gastronomia=self.gastronomia.a_dominio() if self.gastronomia else None,
            entrada=self.entrada.a_dominio() if self.entrada else None,
            alquiler=self.alquiler.a_dominio() if self.alquiler else None,
            transporte=self.transporte.a_dominio() if self.transporte else None,
            pagos=self.pagos.a_dominio() if self.pagos else None,
        )

    @classmethod
    def desde(cls, a: AtributosServicio) -> "AtributosServicioDatos":
        return cls(
            comunes=BloqueComunesDatos.desde(a.comunes),
            alojamiento=BloqueAlojamientoDatos.desde(a.alojamiento) if a.alojamiento else None,
            experiencia=BloqueExperienciaDatos.desde(a.experiencia) if a.experiencia else None,
            gastronomia=BloqueGastronomiaDatos.desde(a.gastronomia) if a.gastronomia else None,
            entrada=BloqueEntradaDatos.desde(a.entrada) if a.entrada else None,
            alquiler=BloqueAlquilerDatos.desde(a.alquiler) if a.alquiler else None,
            transporte=BloqueTransporteDatos.desde(a.transporte) if a.transporte else None,
            pagos=BloquePagosDatos.desde(a.pagos) if a.pagos else None,
        )
