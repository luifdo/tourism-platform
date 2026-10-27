from pydantic import BaseModel, ConfigDict

from app.api.schemas.atributos import comun
from app.api.schemas.atributos.tarifa_visitante_datos import TarifaVisitanteDatos
from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.atributos.valores import ServicioEnSitio


class BloqueEntradaDatos(BaseModel):
    """Bloque E."""

    model_config = ConfigDict(extra="forbid")

    tarifas: list[TarifaVisitanteDatos] = []
    temporadas_cierre: TextoTraducidoDatos | None = None
    reglas: TextoTraducidoDatos | None = None
    servicios_en_sitio: list[ServicioEnSitio] = []

    def a_dominio(self) -> BloqueEntrada:
        return BloqueEntrada(
            tarifas=tuple(t.a_dominio() for t in self.tarifas),
            temporadas_cierre=comun.texto(self.temporadas_cierre),
            reglas=comun.texto(self.reglas),
            servicios_en_sitio=tuple(self.servicios_en_sitio),
        )

    @classmethod
    def desde(cls, bloque: BloqueEntrada) -> "BloqueEntradaDatos":
        return cls(
            tarifas=[TarifaVisitanteDatos.desde(t) for t in bloque.tarifas],
            temporadas_cierre=comun.texto_datos(bloque.temporadas_cierre),
            reglas=comun.texto_datos(bloque.reglas),
            servicios_en_sitio=list(bloque.servicios_en_sitio),
        )
