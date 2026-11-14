from datetime import datetime
from uuid import UUID

from valkey.exceptions import ConnectionError as ValkeyConnectionError

from app.application.dto.alerta_en_mapa import AlertaEnMapa
from app.application.dto.criterios_mapa_servicios import CriteriosMapaServicios
from app.application.dto.escala_mapa import EscalaMapa
from app.application.dto.grupo_en_mapa import GrupoEnMapa
from app.application.dto.mapa_servicios import MapaServicios
from app.application.dto.servicio_en_mapa import ServicioEnMapa
from app.application.dto.zona_en_mapa import ZonaEnMapa
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.geo import Bbox, Coordenada
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.infrastructure.cache.cache_versionada import TTL_SEGUNDOS
from app.infrastructure.cache.consulta_mapa_en_cache import ConsultaMapaEnCache
from app.infrastructure.cache.consulta_servicios_en_cache import ConsultaServiciosEnCache

VISTA = Bbox(min_lon=-74.25, min_lat=11.10, max_lon=-74.05, max_lat=11.35)
MAPA = MapaServicios(
    servicios=(
        ServicioEnMapa(
            id=UUID(int=1),
            nombre=TextoTraducido(es="Tour del café", en="Coffee tour"),
            categoria=Categoria.GASTRONOMIA,
            ubicacion=Coordenada(lat=11.14, lon=-74.11),
            calificacion_promedio=4.5,
        ),
    ),
    grupos=(GrupoEnMapa(ubicacion=Coordenada(lat=11.24, lon=-74.21), conteo=12),),
)


class ValkeyEnMemoria:
    def __init__(self, caido: bool = False) -> None:
        self.datos: dict[str, bytes] = {}
        self.ttl: dict[str, int] = {}
        self.caido = caido

    def _revisar(self) -> None:
        if self.caido:
            raise ValkeyConnectionError("sin conexión")

    async def get(self, clave: str) -> bytes | None:
        self._revisar()
        return self.datos.get(clave)

    async def set(self, clave: str, valor: bytes, ex: int) -> None:
        self._revisar()
        self.datos[clave], self.ttl[clave] = valor, ex

    async def incr(self, clave: str) -> int:
        self._revisar()
        self.datos[clave] = str(int(self.datos.get(clave, b"0")) + 1).encode()
        return int(self.datos[clave])


class OrigenContador:
    def __init__(self) -> None:
        self.llamadas = 0

    async def servicios(self, criterios: CriteriosMapaServicios) -> MapaServicios:
        self.llamadas += 1
        return MAPA

    async def zonas(self, vista: Bbox | None, escala: EscalaMapa) -> list[ZonaEnMapa]:
        self.llamadas += 1
        return []

    async def alertas(self, ahora: datetime, vista: Bbox | None) -> list[AlertaEnMapa]:
        self.llamadas += 1
        return []

    async def buscar(self, criterios: object) -> object:  # para la caché de búsqueda
        self.llamadas += 1
        return None


def criterios(zoom: int) -> CriteriosMapaServicios:
    return CriteriosMapaServicios(vista=VISTA, escala=EscalaMapa(zoom))


async def test_los_grupos_salen_de_la_cache_intactos() -> None:
    origen, valkey = OrigenContador(), ValkeyEnMemoria()
    cache = ConsultaMapaEnCache(origen, valkey)  # type: ignore[arg-type]
    assert await cache.servicios(criterios(10)) == MAPA
    assert await cache.servicios(criterios(10)) == MAPA
    assert origen.llamadas == 1
    [clave] = valkey.ttl
    assert clave.startswith("catalog:mapa:0:servicios:") and valkey.ttl[clave] == TTL_SEGUNDOS


async def test_con_zoom_alto_no_se_cachea() -> None:
    origen, valkey = OrigenContador(), ValkeyEnMemoria()
    cache = ConsultaMapaEnCache(origen, valkey)  # type: ignore[arg-type]
    await cache.servicios(criterios(14))
    await cache.servicios(criterios(14))
    assert origen.llamadas == 2 and not valkey.datos


async def test_zonas_y_alertas_van_siempre_al_origen() -> None:
    origen = OrigenContador()
    cache = ConsultaMapaEnCache(origen, ValkeyEnMemoria())  # type: ignore[arg-type]
    for _ in range(2):
        await cache.zonas(VISTA, EscalaMapa(10))
        await cache.alertas(datetime.now(), VISTA)
    assert origen.llamadas == 4


async def test_invalidar_la_busqueda_invalida_tambien_el_mapa() -> None:
    origen, valkey = OrigenContador(), ValkeyEnMemoria()
    mapa = ConsultaMapaEnCache(origen, valkey)  # type: ignore[arg-type]
    busqueda = ConsultaServiciosEnCache(origen, valkey)  # type: ignore[arg-type]
    await mapa.servicios(criterios(10))
    await busqueda.invalidar()
    await mapa.servicios(criterios(10))
    assert origen.llamadas == 2


async def test_valkey_caido_no_rompe_el_mapa() -> None:
    origen = OrigenContador()
    cache = ConsultaMapaEnCache(origen, ValkeyEnMemoria(caido=True))  # type: ignore[arg-type]
    assert await cache.servicios(criterios(10)) == MAPA
