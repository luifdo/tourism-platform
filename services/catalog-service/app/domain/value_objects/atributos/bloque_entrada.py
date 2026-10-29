from dataclasses import dataclass
from typing import Any

from app.domain.value_objects.atributos import comun
from app.domain.value_objects.atributos.tarifa_visitante import TarifaVisitante
from app.domain.value_objects.atributos.valores import ServicioEnSitio
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class BloqueEntrada:
    """Bloque E: entradas a parques, playas, museos, sitios y eventos.

    Sin tarifas por visitante se cobra `tarifa_base` a todos.
    """

    tarifas: tuple[TarifaVisitante, ...] = ()
    temporadas_cierre: TextoTraducido | None = None
    reglas: TextoTraducido | None = None
    servicios_en_sitio: tuple[ServicioEnSitio, ...] = ()

    def __post_init__(self) -> None:
        comun.sin_repetidos((t.tipo_visitante for t in self.tarifas), "tarifas")
        comun.sin_repetidos(self.servicios_en_sitio, "servicios_en_sitio")

    def a_json(self) -> dict[str, Any]:
        return comun.sin_nulos(
            {
                "tarifas": [t.a_json() for t in self.tarifas],
                "temporadas_cierre": comun.texto_a_json(self.temporadas_cierre),
                "reglas": comun.texto_a_json(self.reglas),
                "servicios_en_sitio": comun.enums_a_json(self.servicios_en_sitio),
            }
        )

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "BloqueEntrada":
        return cls(
            tarifas=tuple(TarifaVisitante.desde_json(t) for t in datos.get("tarifas", ())),
            temporadas_cierre=comun.texto_desde_json(datos.get("temporadas_cierre")),
            reglas=comun.texto_desde_json(datos.get("reglas")),
            servicios_en_sitio=comun.enums_desde_json(
                ServicioEnSitio, datos.get("servicios_en_sitio")
            ),
        )
