from dataclasses import dataclass, field
from typing import Any

from app.domain.errors import DatoInvalido
from app.domain.value_objects.atributos.bloque_alojamiento import BloqueAlojamiento
from app.domain.value_objects.atributos.bloque_alquiler import BloqueAlquiler
from app.domain.value_objects.atributos.bloque_comunes import BloqueComunes
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.atributos.bloque_experiencia import BloqueExperiencia
from app.domain.value_objects.atributos.bloque_gastronomia import BloqueGastronomia
from app.domain.value_objects.atributos.bloque_pagos import BloquePagos
from app.domain.value_objects.atributos.bloque_transporte import BloqueTransporte
from app.domain.value_objects.atributos.valores import BloqueAtributos
from app.domain.value_objects.tipo_servicio import TipoServicio

_CLASES: dict[BloqueAtributos, Any] = {
    BloqueAtributos.ALOJAMIENTO: BloqueAlojamiento,
    BloqueAtributos.EXPERIENCIA: BloqueExperiencia,
    BloqueAtributos.GASTRONOMIA: BloqueGastronomia,
    BloqueAtributos.ENTRADA: BloqueEntrada,
    BloqueAtributos.ALQUILER: BloqueAlquiler,
    BloqueAtributos.TRANSPORTE: BloqueTransporte,
    BloqueAtributos.PAGOS: BloquePagos,
}


@dataclass(frozen=True, slots=True)
class AtributosServicio:
    """Lo propio de cada tipo de servicio (columna JSONB `atributos`).

    Las columnas comunes (nombre, ubicación, tarifa...) siguen siendo relacionales; aquí va
    lo que cambia según el tipo, agrupado en bloques. Cada tipo exige su bloque principal y
    rechaza los que no le corresponden (`TipoServicio.regla`).
    """

    comunes: BloqueComunes = field(default_factory=BloqueComunes)
    alojamiento: BloqueAlojamiento | None = None
    experiencia: BloqueExperiencia | None = None
    gastronomia: BloqueGastronomia | None = None
    entrada: BloqueEntrada | None = None
    alquiler: BloqueAlquiler | None = None
    transporte: BloqueTransporte | None = None
    pagos: BloquePagos | None = None

    def presentes(self) -> set[BloqueAtributos]:
        return {BloqueAtributos.COMUNES} | {
            b for b in _CLASES if getattr(self, b.value) is not None
        }

    def validar_para(self, tipo: TipoServicio) -> None:
        regla = tipo.regla
        if regla.principal not in self.presentes():
            raise DatoInvalido(
                campo=f"atributos.{regla.principal.value}", regla="bloque_obligatorio", tipo=tipo
            )
        sobrantes = self.presentes() - regla.permitidos
        if sobrantes:
            bloque = sorted(sobrantes)[0]
            raise DatoInvalido(
                campo=f"atributos.{bloque.value}", regla="bloque_no_permitido", tipo=tipo
            )

    def a_json(self) -> dict[str, Any]:
        datos = {BloqueAtributos.COMUNES.value: self.comunes.a_json()}
        for bloque in _CLASES:
            valor = getattr(self, bloque.value)
            if valor is not None:
                datos[bloque.value] = valor.a_json()
        return datos

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "AtributosServicio":
        bloques = {
            b.value: clase.desde_json(datos[b.value])
            for b, clase in _CLASES.items()
            if datos.get(b.value) is not None
        }
        return cls(
            comunes=BloqueComunes.desde_json(datos.get(BloqueAtributos.COMUNES.value, {})),
            **bloques,
        )
