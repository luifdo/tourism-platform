from dataclasses import dataclass

from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class ZonaResumen:
    codigo: str
    nombre: TextoTraducido
