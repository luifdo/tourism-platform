from pydantic import BaseModel, ConfigDict

from app.api.schemas.atributos import comun
from app.api.schemas.atributos.comun import Idiomas
from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.value_objects.atributos.bloque_experiencia import BloqueExperiencia
from app.domain.value_objects.atributos.valores import NivelFisico


class BloqueExperienciaDatos(BaseModel):
    """Bloque C."""

    model_config = ConfigDict(extra="forbid")

    duracion_minutos: int
    nivel_fisico: NivelFisico
    punto_encuentro: TextoTraducidoDatos | None = None
    salidas_por_dia: int | None = None
    edad_minima: int | None = None
    grupo_minimo: int | None = None
    grupo_maximo: int | None = None
    incluye_guia: bool = False
    idiomas_guia: Idiomas = []
    incluye_transporte: bool = False
    incluye_equipo: bool = False
    que_llevar: TextoTraducidoDatos | None = None
    requisitos: TextoTraducidoDatos | None = None

    def a_dominio(self) -> BloqueExperiencia:
        return BloqueExperiencia(
            duracion_minutos=self.duracion_minutos,
            nivel_fisico=self.nivel_fisico,
            punto_encuentro=comun.texto(self.punto_encuentro),
            salidas_por_dia=self.salidas_por_dia,
            edad_minima=self.edad_minima,
            grupo_minimo=self.grupo_minimo,
            grupo_maximo=self.grupo_maximo,
            incluye_guia=self.incluye_guia,
            idiomas_guia=tuple(self.idiomas_guia),
            incluye_transporte=self.incluye_transporte,
            incluye_equipo=self.incluye_equipo,
            que_llevar=comun.texto(self.que_llevar),
            requisitos=comun.texto(self.requisitos),
        )

    @classmethod
    def desde(cls, bloque: BloqueExperiencia) -> "BloqueExperienciaDatos":
        return cls(
            duracion_minutos=bloque.duracion_minutos,
            nivel_fisico=bloque.nivel_fisico,
            punto_encuentro=comun.texto_datos(bloque.punto_encuentro),
            salidas_por_dia=bloque.salidas_por_dia,
            edad_minima=bloque.edad_minima,
            grupo_minimo=bloque.grupo_minimo,
            grupo_maximo=bloque.grupo_maximo,
            incluye_guia=bloque.incluye_guia,
            idiomas_guia=list(bloque.idiomas_guia),
            incluye_transporte=bloque.incluye_transporte,
            incluye_equipo=bloque.incluye_equipo,
            que_llevar=comun.texto_datos(bloque.que_llevar),
            requisitos=comun.texto_datos(bloque.requisitos),
        )
