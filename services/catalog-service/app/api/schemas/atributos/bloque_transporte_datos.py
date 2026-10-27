from pydantic import BaseModel, ConfigDict

from app.api.schemas.atributos import comun
from app.api.schemas.atributos.comun import Hora
from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.value_objects.atributos.bloque_transporte import BloqueTransporte


class BloqueTransporteDatos(BaseModel):
    """Bloque G."""

    model_config = ConfigDict(extra="forbid")

    origen: TextoTraducidoDatos
    destino: TextoTraducidoDatos
    duracion_minutos: int
    capacidad_vehiculo: int
    horarios_salida: list[Hora] = []
    incluye_chaleco_salvavidas: bool | None = None

    def a_dominio(self) -> BloqueTransporte:
        return BloqueTransporte(
            origen=self.origen.a_dominio(),
            destino=self.destino.a_dominio(),
            duracion_minutos=self.duracion_minutos,
            capacidad_vehiculo=self.capacidad_vehiculo,
            horarios_salida=tuple(comun.hora(h) for h in self.horarios_salida),
            incluye_chaleco_salvavidas=self.incluye_chaleco_salvavidas,
        )

    @classmethod
    def desde(cls, bloque: BloqueTransporte) -> "BloqueTransporteDatos":
        return cls(
            origen=TextoTraducidoDatos.desde(bloque.origen),
            destino=TextoTraducidoDatos.desde(bloque.destino),
            duracion_minutos=bloque.duracion_minutos,
            capacidad_vehiculo=bloque.capacidad_vehiculo,
            horarios_salida=[comun.hora_texto(h) for h in bloque.horarios_salida],
            incluye_chaleco_salvavidas=bloque.incluye_chaleco_salvavidas,
        )
