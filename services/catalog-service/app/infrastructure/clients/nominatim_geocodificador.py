"""Geocodificación con Nominatim de OpenStreetMap (implementa Geocodificador).

Cumple la política de uso de nominatim.openstreetmap.org: User-Agent propio, máximo una
petición por segundo (LimitadorPorSegundo) y caché de resultados (GeocodificadorEnCache).
Prioriza resultados en la zona de Santa Marta sin excluir el resto de Colombia.
"""

import logging

import httpx

from app.application.dto.candidato_direccion import CandidatoDireccion
from app.application.errores import DependenciaNoDisponible
from app.domain.errors import DatoInvalido
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.idioma import Idioma
from app.infrastructure.clients.limitador_por_segundo import LimitadorPorSegundo

logger = logging.getLogger(__name__)

MAXIMO_CANDIDATOS = 5
# minLon,maxLat,maxLon,minLat: Santa Marta, Minca y el Tayrona.
_VISTA_SANTA_MARTA = "-74.35,11.40,-73.85,11.05"


class NominatimGeocodificador:
    def __init__(
        self,
        cliente: httpx.AsyncClient,
        limitador: LimitadorPorSegundo,
        email_contacto: str | None = None,
    ) -> None:
        self._cliente = cliente
        self._limitador = limitador
        self._email = email_contacto

    async def buscar(self, direccion: str, idioma: Idioma) -> list[CandidatoDireccion]:
        if not await self._limitador.turno():
            raise DependenciaNoDisponible(servicio="nominatim", motivo="limite_de_peticiones")
        parametros = {
            "q": direccion,
            "format": "jsonv2",
            "limit": MAXIMO_CANDIDATOS,
            "countrycodes": "co",
            "viewbox": _VISTA_SANTA_MARTA,
            "bounded": 0,
            "accept-language": idioma.value,
        }
        if self._email:
            parametros["email"] = self._email
        try:
            respuesta = await self._cliente.get("/search", params=parametros)
            respuesta.raise_for_status()
            resultados = respuesta.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Nominatim no respondió bien: %s", exc)
            raise DependenciaNoDisponible(servicio="nominatim") from exc
        return [c for c in (self._candidato(r) for r in resultados) if c is not None]

    @staticmethod
    def _candidato(resultado: dict) -> CandidatoDireccion | None:
        try:
            ubicacion = Coordenada(lat=float(resultado["lat"]), lon=float(resultado["lon"]))
            return CandidatoDireccion(ubicacion=ubicacion, etiqueta=str(resultado["display_name"]))
        except (KeyError, TypeError, ValueError, DatoInvalido):
            return None  # un resultado raro no debe tumbar los demás
