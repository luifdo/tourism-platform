from pydantic import BaseModel, ConfigDict

from app.api.schemas.atributos import comun
from app.api.schemas.atributos.comun import Pesos
from app.domain.value_objects.atributos.bloque_gastronomia import BloqueGastronomia
from app.domain.value_objects.atributos.valores import OpcionDietaria, TipoCocina


class BloqueGastronomiaDatos(BaseModel):
    """Bloque D."""

    model_config = ConfigDict(extra="forbid")

    tipos_cocina: list[TipoCocina]
    opciones_dietarias: list[OpcionDietaria] = []
    precio_min_persona: Pesos | None = None
    precio_max_persona: Pesos | None = None
    requiere_reserva: bool = False
    puestos: int | None = None
    domicilio: bool = False

    def a_dominio(self) -> BloqueGastronomia:
        return BloqueGastronomia(
            tipos_cocina=tuple(self.tipos_cocina),
            opciones_dietarias=tuple(self.opciones_dietarias),
            precio_min_persona=comun.tarifa(self.precio_min_persona),
            precio_max_persona=comun.tarifa(self.precio_max_persona),
            requiere_reserva=self.requiere_reserva,
            puestos=self.puestos,
            domicilio=self.domicilio,
        )

    @classmethod
    def desde(cls, bloque: BloqueGastronomia) -> "BloqueGastronomiaDatos":
        return cls(
            tipos_cocina=list(bloque.tipos_cocina),
            opciones_dietarias=list(bloque.opciones_dietarias),
            precio_min_persona=comun.pesos(bloque.precio_min_persona),
            precio_max_persona=comun.pesos(bloque.precio_max_persona),
            requiere_reserva=bloque.requiere_reserva,
            puestos=bloque.puestos,
            domicilio=bloque.domicilio,
        )
