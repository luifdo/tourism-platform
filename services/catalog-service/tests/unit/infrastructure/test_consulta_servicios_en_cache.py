from datetime import date, datetime
from uuid import UUID

from valkey.exceptions import ConnectionError as ValkeyConnectionError

from app.application.dto.criterios_busqueda import CriteriosBusqueda
from app.application.dto.filtros_servicio import FiltrosServicio
from app.application.dto.pagina_servicios import PaginaServicios
from app.application.dto.servicio_detalle import ServicioDetalle
from app.domain.value_objects.idioma import Idioma
from app.infrastructure.cache.cache_versionada import CLAVE_GENERACION, TTL_SEGUNDOS
from app.infrastructure.cache.consulta_servicios_en_cache import ConsultaServiciosEnCache


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

    async def buscar(self, criterios: CriteriosBusqueda) -> PaginaServicios:
        self.llamadas += 1
        return PaginaServicios(items=(), pagina=criterios.pagina, tamano=criterios.tamano, total=7)

    async def detalle(self, servicio_id: UUID, ahora: datetime) -> ServicioDetalle | None:
        self.llamadas += 1
        return None


ES = CriteriosBusqueda(idioma=Idioma.ES)
EN = CriteriosBusqueda(idioma=Idioma.EN)


async def test_segunda_busqueda_igual_sale_de_la_cache() -> None:
    origen, valkey = OrigenContador(), ValkeyEnMemoria()
    cache = ConsultaServiciosEnCache(origen, valkey)  # type: ignore[arg-type]
    primera = await cache.buscar(ES)
    segunda = await cache.buscar(ES)
    assert origen.llamadas == 1 and primera == segunda
    assert set(valkey.ttl.values()) == {TTL_SEGUNDOS}


async def test_idioma_distinto_es_otra_clave() -> None:
    origen = OrigenContador()
    cache = ConsultaServiciosEnCache(origen, ValkeyEnMemoria())  # type: ignore[arg-type]
    await cache.buscar(ES)
    await cache.buscar(EN)
    assert origen.llamadas == 2


async def test_invalidar_cambia_de_generacion() -> None:
    origen, valkey = OrigenContador(), ValkeyEnMemoria()
    cache = ConsultaServiciosEnCache(origen, valkey)  # type: ignore[arg-type]
    await cache.buscar(ES)
    await cache.invalidar()
    await cache.buscar(ES)
    assert origen.llamadas == 2 and valkey.datos[CLAVE_GENERACION] == b"1"


async def test_valkey_caido_no_rompe_la_busqueda() -> None:
    origen = OrigenContador()
    cache = ConsultaServiciosEnCache(origen, ValkeyEnMemoria(caido=True))  # type: ignore[arg-type]
    assert (await cache.buscar(ES)).total == 7
    await cache.invalidar()  # tampoco falla
    assert origen.llamadas == 1


async def test_el_detalle_no_se_cachea() -> None:
    origen = OrigenContador()
    cache = ConsultaServiciosEnCache(origen, ValkeyEnMemoria())  # type: ignore[arg-type]
    await cache.detalle(UUID(int=1), datetime.now())
    await cache.detalle(UUID(int=1), datetime.now())
    assert origen.llamadas == 2


async def test_filtros_de_atributos_son_otra_clave() -> None:
    origen = OrigenContador()
    cache = ConsultaServiciosEnCache(origen, ValkeyEnMemoria())  # type: ignore[arg-type]
    await cache.buscar(ES)
    await cache.buscar(
        CriteriosBusqueda(idioma=Idioma.ES, filtros=FiltrosServicio(ofrece_credito=True))
    )
    assert origen.llamadas == 2


async def test_entrada_ilegible_cuenta_como_fallo_y_se_reescribe() -> None:
    # Por ejemplo, guardada antes de un despliegue que cambió el resumen.
    origen, valkey = OrigenContador(), ValkeyEnMemoria()
    cache = ConsultaServiciosEnCache(origen, valkey)  # type: ignore[arg-type]
    await cache.buscar(ES)
    [clave] = [k for k in valkey.datos if k.startswith("catalog:buscar:")]
    valkey.datos[clave] = b'{"items": [{"forma": "vieja"}]}'
    pagina = await cache.buscar(ES)
    assert pagina.total == 7 and origen.llamadas == 2
    assert b"vieja" not in valkey.datos[clave]


async def test_con_fecha_no_se_cachea() -> None:
    # Los cupos cambian con cada reserva: cada búsqueda con fecha va a PostGIS.
    origen, valkey = OrigenContador(), ValkeyEnMemoria()
    cache = ConsultaServiciosEnCache(origen, valkey)  # type: ignore[arg-type]
    con_fecha = CriteriosBusqueda(
        idioma=Idioma.ES, filtros=FiltrosServicio(fecha=date(2026, 11, 5))
    )
    await cache.buscar(con_fecha)
    await cache.buscar(con_fecha)
    assert origen.llamadas == 2 and not any(k.startswith("catalog:buscar") for k in valkey.datos)
