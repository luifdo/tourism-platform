from app.application.dto.candidato_direccion import CandidatoDireccion
from app.application.ports.geocodificador import Geocodificador
from app.domain.errors import DatoInvalido
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.idioma import Idioma


class GeocodificarDireccion:
    """Ayuda al registrar una oferta: sugiere coordenadas para una dirección (Nominatim)."""

    def __init__(self, geocodificador: Geocodificador) -> None:
        self._geocodificador = geocodificador

    async def execute(
        self, identidad: Identidad, direccion: str, idioma: Idioma
    ) -> list[CandidatoDireccion]:
        identidad.exigir_rol(Rol.PRESTADOR)
        direccion = " ".join(direccion.split())
        if not 5 <= len(direccion) <= 200:
            raise DatoInvalido(campo="direccion", regla="rango", minimo=5, maximo=200)
        return await self._geocodificador.buscar(direccion, idioma)
