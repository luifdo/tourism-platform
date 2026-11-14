from dataclasses import dataclass
from typing import Any

from app.domain.errors import DatoInvalido
from app.domain.value_objects.atributos import comun
from app.domain.value_objects.atributos.valores import NivelFisico
from app.domain.value_objects.texto_traducido import TextoTraducido

DURACION_MAXIMA_MIN = 14 * 24 * 60  # trekkings de varios días, como Ciudad Perdida


@dataclass(frozen=True, slots=True)
class BloqueExperiencia:
    """Bloque C: tours, senderismo, deportes, avistamiento y experiencias culturales."""

    duracion_minutos: int
    nivel_fisico: NivelFisico
    punto_encuentro: TextoTraducido | None = None
    salidas_por_dia: int | None = None
    edad_minima: int | None = None
    grupo_minimo: int | None = None
    grupo_maximo: int | None = None
    incluye_guia: bool = False
    idiomas_guia: tuple[str, ...] = ()
    incluye_transporte: bool = False
    incluye_equipo: bool = False
    que_llevar: TextoTraducido | None = None
    requisitos: TextoTraducido | None = None

    def __post_init__(self) -> None:
        comun.en_rango(self.duracion_minutos, "duracion_minutos", 1, DURACION_MAXIMA_MIN)
        comun.en_rango(self.salidas_por_dia, "salidas_por_dia", 1, 48)
        comun.en_rango(self.edad_minima, "edad_minima", 0, 99)
        comun.en_rango(self.grupo_minimo, "grupo_minimo", 1, 1000)
        comun.en_rango(self.grupo_maximo, "grupo_maximo", 1, 1000)
        comun.no_mayor(self.grupo_minimo, self.grupo_maximo, "grupo_minimo", "grupo_maximo")
        comun.idiomas(self.idiomas_guia, "idiomas_guia")
        if self.idiomas_guia and not self.incluye_guia:
            raise DatoInvalido(campo="idiomas_guia", regla="requiere", requiere="incluye_guia")

    def a_json(self) -> dict[str, Any]:
        return comun.sin_nulos(
            {
                "duracion_minutos": self.duracion_minutos,
                "nivel_fisico": self.nivel_fisico.value,
                "punto_encuentro": comun.texto_a_json(self.punto_encuentro),
                "salidas_por_dia": self.salidas_por_dia,
                "edad_minima": self.edad_minima,
                "grupo_minimo": self.grupo_minimo,
                "grupo_maximo": self.grupo_maximo,
                "incluye_guia": self.incluye_guia,
                "idiomas_guia": list(self.idiomas_guia),
                "incluye_transporte": self.incluye_transporte,
                "incluye_equipo": self.incluye_equipo,
                "que_llevar": comun.texto_a_json(self.que_llevar),
                "requisitos": comun.texto_a_json(self.requisitos),
            }
        )

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "BloqueExperiencia":
        return cls(
            duracion_minutos=datos["duracion_minutos"],
            nivel_fisico=NivelFisico(datos["nivel_fisico"]),
            punto_encuentro=comun.texto_desde_json(datos.get("punto_encuentro")),
            salidas_por_dia=datos.get("salidas_por_dia"),
            edad_minima=datos.get("edad_minima"),
            grupo_minimo=datos.get("grupo_minimo"),
            grupo_maximo=datos.get("grupo_maximo"),
            incluye_guia=datos.get("incluye_guia", False),
            idiomas_guia=tuple(datos.get("idiomas_guia", ())),
            incluye_transporte=datos.get("incluye_transporte", False),
            incluye_equipo=datos.get("incluye_equipo", False),
            que_llevar=comun.texto_desde_json(datos.get("que_llevar")),
            requisitos=comun.texto_desde_json(datos.get("requisitos")),
        )
