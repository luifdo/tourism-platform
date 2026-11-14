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
        if not 5 <= len(direccion) <= 200:
            raise DatoInvalido(campo="direccion", regla="rango", minimo=5, maximo=200)
        # El rango se valida sobre lo recibido, como dice el contrato. Si al juntar los espacios
        # (Python cuenta también \r o \x1d) queda muy poco, no hay nada útil que buscar: sin
        # sugerencias y sin gastar el cupo de Nominatim.
        direccion = " ".join(direccion.split())
        if len(direccion) < 5:
            return []
        return await self._geocodificador.buscar(direccion, idioma)
