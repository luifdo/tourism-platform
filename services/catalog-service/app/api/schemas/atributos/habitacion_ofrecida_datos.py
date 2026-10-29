from pydantic import BaseModel, ConfigDict

from app.domain.value_objects.atributos.habitacion_ofrecida import HabitacionOfrecida
from app.domain.value_objects.atributos.valores import TipoHabitacion


class HabitacionOfrecidaDatos(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: TipoHabitacion
    capacidad_personas: int
    cantidad: int = 1

    def a_dominio(self) -> HabitacionOfrecida:
        return HabitacionOfrecida(self.tipo, self.capacidad_personas, self.cantidad)

    @classmethod
    def desde(cls, habitacion: HabitacionOfrecida) -> "HabitacionOfrecidaDatos":
        return cls(
            tipo=habitacion.tipo,
            capacidad_personas=habitacion.capacidad_personas,
            cantidad=habitacion.cantidad,
        )
