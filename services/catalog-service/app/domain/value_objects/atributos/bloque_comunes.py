from dataclasses import dataclass
from typing import Any

from app.domain.value_objects.atributos import comun
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class BloqueComunes:
    """Bloque A, para todos los tipos. `None` en un sí/no significa "no informado"."""

    horario: TextoTraducido | None = None
    idiomas_atencion: tuple[str, ...] = ("es",)
    incluye: TextoTraducido | None = None
    no_incluye: TextoTraducido | None = None
    accesible: bool | None = None
    mascotas: bool | None = None
    apto_ninos: bool | None = None
    practicas_sostenibles: TextoTraducido | None = None
    certificacion_sostenible: str | None = None

    def __post_init__(self) -> None:
        comun.no_vacio(self.idiomas_atencion, "idiomas_atencion")
        comun.idiomas(self.idiomas_atencion, "idiomas_atencion")
        if self.certificacion_sostenible is not None:
            certificacion = self.certificacion_sostenible.strip()
            comun.en_rango(len(certificacion), "certificacion_sostenible", 1, 100)
            object.__setattr__(self, "certificacion_sostenible", certificacion)

    def a_json(self) -> dict[str, Any]:
        return comun.sin_nulos(
            {
                "horario": comun.texto_a_json(self.horario),
                "idiomas_atencion": list(self.idiomas_atencion),
                "incluye": comun.texto_a_json(self.incluye),
                "no_incluye": comun.texto_a_json(self.no_incluye),
                "accesible": self.accesible,
                "mascotas": self.mascotas,
                "apto_ninos": self.apto_ninos,
                "practicas_sostenibles": comun.texto_a_json(self.practicas_sostenibles),
                "certificacion_sostenible": self.certificacion_sostenible,
            }
        )

    @classmethod
    def desde_json(cls, datos: dict[str, Any]) -> "BloqueComunes":
        return cls(
            horario=comun.texto_desde_json(datos.get("horario")),
            idiomas_atencion=tuple(datos.get("idiomas_atencion", ("es",))),
            incluye=comun.texto_desde_json(datos.get("incluye")),
            no_incluye=comun.texto_desde_json(datos.get("no_incluye")),
            accesible=datos.get("accesible"),
            mascotas=datos.get("mascotas"),
            apto_ninos=datos.get("apto_ninos"),
            practicas_sostenibles=comun.texto_desde_json(datos.get("practicas_sostenibles")),
            certificacion_sostenible=datos.get("certificacion_sostenible"),
        )
