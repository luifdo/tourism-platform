from pydantic import BaseModel, ConfigDict

from app.api.schemas.atributos import comun
from app.api.schemas.atributos.comun import Hora
from app.api.schemas.atributos.habitacion_ofrecida_datos import HabitacionOfrecidaDatos
from app.domain.value_objects.atributos.bloque_alojamiento import BloqueAlojamiento
from app.domain.value_objects.atributos.valores import Amenidad


class BloqueAlojamientoDatos(BaseModel):
    """Bloque B."""

    model_config = ConfigDict(extra="forbid")

    check_in: Hora
    check_out: Hora
    habitaciones: list[HabitacionOfrecidaDatos]
    amenidades: list[Amenidad] = []
    desayuno_incluido: bool = False

    def a_dominio(self) -> BloqueAlojamiento:
        return BloqueAlojamiento(
            check_in=comun.hora(self.check_in),
            check_out=comun.hora(self.check_out),
            habitaciones=tuple(h.a_dominio() for h in self.habitaciones),
            amenidades=tuple(self.amenidades),
            desayuno_incluido=self.desayuno_incluido,
        )

    @classmethod
    def desde(cls, bloque: BloqueAlojamiento) -> "BloqueAlojamientoDatos":
        return cls(
            check_in=comun.hora_texto(bloque.check_in),
            check_out=comun.hora_texto(bloque.check_out),
            habitaciones=[HabitacionOfrecidaDatos.desde(h) for h in bloque.habitaciones],
            amenidades=list(bloque.amenidades),
            desayuno_incluido=bloque.desayuno_incluido,
        )
