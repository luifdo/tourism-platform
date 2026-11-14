from typing import Protocol

from app.application.dto.candidato_direccion import CandidatoDireccion
from app.domain.value_objects.idioma import Idioma


class Geocodificador(Protocol):
    async def buscar(self, direccion: str, idioma: Idioma) -> list[CandidatoDireccion]:
        """Hasta 5 candidatos, el más probable primero.

        Lanza DependenciaNoDisponible si el proveedor no responde a tiempo.
        """
        ...
