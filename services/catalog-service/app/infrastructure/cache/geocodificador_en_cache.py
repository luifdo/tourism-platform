"""Caché de geocodificación en Valkey como decorador de Geocodificador.

Una dirección casi nunca cambia de lugar, así que se guarda 7 días: evita repetir llamadas
a Nominatim (lo pide su política de uso) y responde al instante. No depende de la
generación del catálogo. Si Valkey falla, se consulta Nominatim directamente.
"""

import hashlib
import logging

from pydantic import TypeAdapter
from valkey.asyncio import Valkey
from valkey.exceptions import ValkeyError

from app.application.dto.candidato_direccion import CandidatoDireccion
from app.application.ports.geocodificador import Geocodificador
from app.domain.value_objects.idioma import Idioma

logger = logging.getLogger(__name__)

TTL_SEGUNDOS = 7 * 24 * 3600
_FALLAS = (ValkeyError, OSError, TimeoutError)
_candidatos_json = TypeAdapter(list[CandidatoDireccion])


class GeocodificadorEnCache:
    def __init__(self, origen: Geocodificador, valkey: Valkey) -> None:
        self._origen = origen
        self._valkey = valkey

    async def buscar(self, direccion: str, idioma: Idioma) -> list[CandidatoDireccion]:
        huella = hashlib.sha256(direccion.casefold().encode()).hexdigest()[:32]
        clave = f"catalog:geocodificar:{idioma.value}:{huella}"
        try:
            guardado = await self._valkey.get(clave)
        except _FALLAS:
            logger.warning("Valkey no responde; geocodificación sin caché", exc_info=True)
            guardado = None
        if guardado is not None:
            return _candidatos_json.validate_json(guardado)
        candidatos = await self._origen.buscar(direccion, idioma)
        try:
            await self._valkey.set(clave, _candidatos_json.dump_json(candidatos), ex=TTL_SEGUNDOS)
        except _FALLAS:
            logger.warning("No se pudo guardar la geocodificación", exc_info=True)
        return candidatos
