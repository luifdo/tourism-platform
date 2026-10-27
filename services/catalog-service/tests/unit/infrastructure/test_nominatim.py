"""Adaptador de Nominatim con un transporte HTTP simulado: nunca llama a internet."""

import httpx
import pytest

from app.application.errores import DependenciaNoDisponible
from app.domain.value_objects.idioma import Idioma
from app.infrastructure.cache.geocodificador_en_cache import GeocodificadorEnCache
from app.infrastructure.clients.nominatim_geocodificador import NominatimGeocodificador

RESULTADOS = [
    {"lat": "11.2420", "lon": "-74.2110", "display_name": "Parque de los Novios, Santa Marta"},
    {"lat": "fuera", "lon": "-74.1", "display_name": "Resultado roto"},
    {"lat": "11.14", "lon": "-74.11", "display_name": "Minca"},
]


class LimitadorFalso:
    def __init__(self, permite: bool = True) -> None:
        self.permite = permite
        self.turnos = 0

    async def turno(self) -> bool:
        self.turnos += 1
        return self.permite


class ValkeyEnMemoria:
    def __init__(self) -> None:
        self.datos: dict[str, bytes] = {}

    async def get(self, clave: str) -> bytes | None:
        return self.datos.get(clave)

    async def set(self, clave: str, valor: bytes, ex: int) -> None:
        self.datos[clave] = valor


def geocodificador(manejador, limitador=None) -> NominatimGeocodificador:  # noqa: ANN001
    cliente = httpx.AsyncClient(
        base_url="https://nominatim.test",
        transport=httpx.MockTransport(manejador),
        headers={"User-Agent": "turismo-prueba/1.0"},
    )
    return NominatimGeocodificador(cliente, limitador or LimitadorFalso(), "equipo@turismo.test")


async def test_parametros_de_la_politica_de_uso_y_candidatos_validos() -> None:
    recibidas: list[httpx.Request] = []

    def manejador(peticion: httpx.Request) -> httpx.Response:
        recibidas.append(peticion)
        return httpx.Response(200, json=RESULTADOS)

    candidatos = await geocodificador(manejador).buscar("Parque de los Novios", Idioma.EN)
    assert [c.etiqueta for c in candidatos] == ["Parque de los Novios, Santa Marta", "Minca"]
    assert candidatos[0].ubicacion.lat == 11.242 and candidatos[0].ubicacion.lon == -74.211
    [peticion] = recibidas
    assert peticion.headers["user-agent"] == "turismo-prueba/1.0"
    parametros = peticion.url.params
    assert parametros["countrycodes"] == "co" and parametros["limit"] == "5"
    assert parametros["accept-language"] == "en" and parametros["email"] == "equipo@turismo.test"


@pytest.mark.parametrize(
    "respuesta",
    [httpx.Response(503), httpx.Response(429), httpx.Response(200, text="<html>")],
)
async def test_fallas_del_proveedor_son_503(respuesta: httpx.Response) -> None:
    with pytest.raises(DependenciaNoDisponible):
        await geocodificador(lambda _: respuesta).buscar("Calle 22", Idioma.ES)


async def test_timeout_es_503() -> None:
    def lento(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento", request=peticion)

    with pytest.raises(DependenciaNoDisponible):
        await geocodificador(lento).buscar("Calle 22", Idioma.ES)


async def test_sin_turno_no_llama() -> None:
    llamadas = []
    limitador = LimitadorFalso(permite=False)
    with pytest.raises(DependenciaNoDisponible):
        await geocodificador(lambda p: llamadas.append(p), limitador).buscar("Calle 22", Idioma.ES)
    assert llamadas == []


async def test_la_cache_evita_la_segunda_llamada() -> None:
    llamadas = []

    def manejador(peticion: httpx.Request) -> httpx.Response:
        llamadas.append(peticion)
        return httpx.Response(200, json=RESULTADOS[:1])

    cache = GeocodificadorEnCache(geocodificador(manejador), ValkeyEnMemoria())  # type: ignore[arg-type]
    primera = await cache.buscar("Parque de los Novios", Idioma.ES)
    segunda = await cache.buscar("PARQUE DE LOS NOVIOS", Idioma.ES)  # misma dirección
    assert primera == segunda and len(llamadas) == 1
    await cache.buscar("Parque de los Novios", Idioma.EN)  # otro idioma: otra etiqueta
    assert len(llamadas) == 2
