from pydantic import BaseModel, ConfigDict

from app.api.schemas.atributos import comun
from app.api.schemas.atributos.comun import Idiomas
from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.value_objects.atributos.bloque_comunes import BloqueComunes


class BloqueComunesDatos(BaseModel):
    """Bloque A. `null` en un sí/no significa "no informado"."""

    model_config = ConfigDict(extra="forbid")

    horario: TextoTraducidoDatos | None = None
    idiomas_atencion: Idiomas = ["es"]
    incluye: TextoTraducidoDatos | None = None
    no_incluye: TextoTraducidoDatos | None = None
    accesible: bool | None = None
    mascotas: bool | None = None
    apto_ninos: bool | None = None
    practicas_sostenibles: TextoTraducidoDatos | None = None
    certificacion_sostenible: str | None = None

    def a_dominio(self) -> BloqueComunes:
        return BloqueComunes(
            horario=comun.texto(self.horario),
            idiomas_atencion=tuple(self.idiomas_atencion),
            incluye=comun.texto(self.incluye),
            no_incluye=comun.texto(self.no_incluye),
            accesible=self.accesible,
            mascotas=self.mascotas,
            apto_ninos=self.apto_ninos,
            practicas_sostenibles=comun.texto(self.practicas_sostenibles),
            certificacion_sostenible=self.certificacion_sostenible,
        )

    @classmethod
    def desde(cls, bloque: BloqueComunes) -> "BloqueComunesDatos":
        return cls(
            horario=comun.texto_datos(bloque.horario),
            idiomas_atencion=list(bloque.idiomas_atencion),
            incluye=comun.texto_datos(bloque.incluye),
            no_incluye=comun.texto_datos(bloque.no_incluye),
            accesible=bloque.accesible,
            mascotas=bloque.mascotas,
            apto_ninos=bloque.apto_ninos,
            practicas_sostenibles=comun.texto_datos(bloque.practicas_sostenibles),
            certificacion_sostenible=bloque.certificacion_sostenible,
        )
