"""Caché de búsqueda contra un Valkey real."""

from collections.abc import AsyncIterator

import pytest
from valkey.asyncio import Valkey

from app.application.dto.criterios_busqueda import CriteriosBusqueda
from app.application.dto.pagina_servicios import PaginaServicios
from app.domain.value_objects.idioma import Idioma
from app.infrastructure.cache.cache_versionada import TTL_SEGUNDOS
from app.infrastructure.cache.consulta_servicios_en_cache import ConsultaServiciosEnCache

pytestmark = pytest.mark.integration


@pytest.fixture
async def valkey(valkey_url: str) -> AsyncIterator[Valkey]:
    cliente = Valkey.from_url(valkey_url)
    await cliente.flushdb()
    yield cliente
    await cliente.aclose()


class Origen:
    def __init__(self) -> None:
        self.llamadas = 0

    async def buscar(self, criterios: CriteriosBusqueda) -> PaginaServicios:
        self.llamadas += 1
        return PaginaServicios(items=(), pagina=1, tamano=20, total=self.llamadas)

    async def detalle(self, *args: object) -> None:
        return None


async def test_guarda_con_ttl_y_responde_desde_valkey(valkey: Valkey) -> None:
    origen = Origen()
    cache = ConsultaServiciosEnCache(origen, valkey)  # type: ignore[arg-type]
    criterios = CriteriosBusqueda(idioma=Idioma.ES, texto="playa")

    assert (await cache.buscar(criterios)).total == 1
    assert (await cache.buscar(criterios)).total == 1  # desde la caché
    claves = await valkey.keys("catalog:buscar:0:es:*")
    assert len(claves) == 1
    assert 0 < await valkey.ttl(claves[0]) <= TTL_SEGUNDOS


async def test_invalidar_obliga_a_consultar_de_nuevo(valkey: Valkey) -> None:
    origen = Origen()
    cache = ConsultaServiciosEnCache(origen, valkey)  # type: ignore[arg-type]
    criterios = CriteriosBusqueda(idioma=Idioma.EN)
    await cache.buscar(criterios)
    await cache.invalidar()
    assert (await cache.buscar(criterios)).total == 2
    assert await valkey.keys("catalog:buscar:1:en:*")


async def test_valkey_inalcanzable_no_rompe() -> None:
    origen = Origen()
    caido = Valkey.from_url("redis://127.0.0.1:1/0", socket_timeout=0.2, socket_connect_timeout=0.2)
    cache = ConsultaServiciosEnCache(origen, caido)
    assert (await cache.buscar(CriteriosBusqueda(idioma=Idioma.ES))).total == 1
    await caido.aclose()
