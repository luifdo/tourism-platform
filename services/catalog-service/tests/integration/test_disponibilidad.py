"""Disponibilidad por eventos contra RabbitMQ y PostGIS reales: el consumidor guarda los cupos
de booking y la búsqueda y el mapa filtran por fecha y personas sin llamar a booking.

`bus` y `consumir` (conftest) dan a cada prueba su propia cola y esperas de reintento cortas.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.criterios_busqueda import CriteriosBusqueda
from app.application.dto.criterios_mapa_servicios import CriteriosMapaServicios
from app.application.dto.escala_mapa import EscalaMapa
from app.application.dto.filtros_servicio import FiltrosServicio
from app.application.use_cases.aplicar_disponibilidad import AplicarDisponibilidad
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Bbox, Coordenada
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.messaging.manejador_disponibilidad import CLAVES, ManejadorDisponibilidad
from app.infrastructure.persistence.consultas.sql_consulta_mapa import SqlConsultaMapa
from app.infrastructure.persistence.consultas.sql_consulta_servicios import SqlConsultaServicios
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

pytestmark = pytest.mark.integration

Sesiones = async_sessionmaker[AsyncSession]
AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
DIA = date(2026, 11, 5)
VISTA_MINCA = Bbox(min_lon=-74.13, min_lat=11.13, max_lon=-74.10, max_lat=11.16)


def disponibilidad(servicio: UUID, disponibles: int, version: int, totales: int = 10) -> dict:
    return {
        "event_id": str(uuid4()),
        "event_type": "disponibilidad.actualizada",
        "version": 1,
        "occurred_at": AHORA.isoformat(),
        "producer": "booking-service",
        "payload": {
            "servicio_id": str(servicio),
            "fecha": DIA.isoformat(),
            "cupos_totales": totales,
            "cupos_disponibles": disponibles,
            "version": version,
        },
    }


@pytest.fixture
async def servicios(sesiones: Sesiones) -> dict[str, UUID]:
    """Cuatro servicios en Minca: con cupo, lleno, cerrado ese día y sin dato de booking."""
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Minca Viva")

    def nuevo(nombre: str) -> AtractivoServicio:
        return AtractivoServicio.registrar(
            perfil,
            DatosServicio(
                nombre=TextoTraducido(es=nombre),
                descripcion=TextoTraducido(es="Entrada"),
                tipo=TipoServicio.RESERVA_PARQUE,
                ubicacion=Coordenada(lat=11.1426, lon=-74.1178),
                tarifa_base=Tarifa(Decimal("10000")),
                unidad_tarifa=UnidadTarifa.POR_PERSONA,
                capacidad_aforo_diario=50,
                atributos=AtributosServicio(entrada=BloqueEntrada()),
            ),
            "https://s3/",
            AHORA,
        )

    creados = {n: nuevo(n) for n in ("con_cupo", "lleno", "cerrado", "sin_dato")}
    async with SqlUnidadDeTrabajo(sesiones) as uow:
        await uow.prestadores.guardar(perfil)
        for s in creados.values():
            await uow.servicios.guardar(s)
        await uow.confirmar()
    return {n: s.id for n, s in creados.items()}


def manejador(sesiones: Sesiones) -> ManejadorDisponibilidad:
    return ManejadorDisponibilidad(AplicarDisponibilidad(lambda: SqlUnidadDeTrabajo(sesiones)))


async def esperar(condicion: Callable[[], Awaitable[bool]], segundos: float = 10) -> None:
    for _ in range(int(segundos / 0.1)):
        if await condicion():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("La condición no se cumplió a tiempo")


async def publicar_y_esperar(bus: Any, sesiones: Sesiones, *eventos: dict) -> None:
    async def procesados() -> int:
        async with sesiones() as session:
            return await session.scalar(text("SELECT count(*) FROM evento_procesado")) or 0

    antes = await procesados()
    for e in eventos:
        await bus.publicar(e)

    async def listos() -> bool:
        return await procesados() >= antes + len(eventos)

    await esperar(listos)


async def buscar(sesiones: Sesiones, personas: int = 1) -> dict[UUID, tuple[Any, Any]]:
    pagina = await SqlConsultaServicios(sesiones).buscar(
        CriteriosBusqueda(idioma=Idioma.ES, filtros=FiltrosServicio(fecha=DIA, personas=personas))
    )
    return {s.id: (s.cupos_disponibles, s.disponibilidad_confirmada) for s in pagina.items}


async def test_busqueda_y_mapa_filtran_por_los_cupos_de_booking(
    sesiones: Sesiones, servicios: dict[str, UUID], bus: Any, consumir: Any
) -> None:
    await consumir(CLAVES, manejador(sesiones))
    await publicar_y_esperar(
        bus,
        sesiones,
        disponibilidad(servicios["con_cupo"], disponibles=4, version=3),
        disponibilidad(servicios["lleno"], disponibles=0, version=7),
        disponibilidad(servicios["cerrado"], disponibles=0, version=1, totales=0),
    )

    para_dos = await buscar(sesiones, personas=2)
    assert para_dos == {
        servicios["con_cupo"]: (4, True),
        servicios["sin_dato"]: (None, False),  # se muestra, sin confirmar
    }
    # Para 5 personas tampoco alcanza el que tiene 4.
    assert set(await buscar(sesiones, personas=5)) == {servicios["sin_dato"]}

    # Sin fecha no se filtra ni se informa disponibilidad.
    sin_fecha = await SqlConsultaServicios(sesiones).buscar(CriteriosBusqueda(idioma=Idioma.ES))
    assert sin_fecha.total == 4
    assert {s.disponibilidad_confirmada for s in sin_fecha.items} == {None}

    # El mapa usa el mismo filtro, agrupado o no.
    for zoom in (15, 10):
        mapa = await SqlConsultaMapa(sesiones).servicios(
            CriteriosMapaServicios(
                vista=VISTA_MINCA,
                escala=EscalaMapa(zoom),
                filtros=FiltrosServicio(fecha=DIA, personas=2),
            )
        )
        assert len(mapa.servicios) + sum(g.conteo for g in mapa.grupos) == 2


async def test_una_version_vieja_no_pisa_la_nueva(
    sesiones: Sesiones, servicios: dict[str, UUID], bus: Any, consumir: Any
) -> None:
    await consumir(CLAVES, manejador(sesiones))
    servicio = servicios["con_cupo"]
    # Una reserva tomó cupos (versión 5) y llega tarde la versión 4, de antes de la reserva.
    await publicar_y_esperar(
        bus,
        sesiones,
        disponibilidad(servicio, disponibles=1, version=5),
        disponibilidad(servicio, disponibles=9, version=4),
    )
    assert (await buscar(sesiones))[servicio] == (1, True)


async def test_cupos_incoherentes_van_a_la_dlq(
    sesiones: Sesiones, servicios: dict[str, UUID], bus: Any, consumir: Any
) -> None:
    await consumir(CLAVES, manejador(sesiones))
    await bus.publicar(disponibilidad(servicios["con_cupo"], disponibles=12, version=1, totales=10))
    mensaje = await bus.de_la_dlq()
    assert mensaje.routing_key == "disponibilidad.actualizada"
    assert (await buscar(sesiones))[servicios["con_cupo"]] == (None, False)
