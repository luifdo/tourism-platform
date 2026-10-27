"""Capacidad de carga (UC24), mapa de calor (RF-07) y limpieza de disponibilidad, con
PostGIS y Valkey reales."""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from valkey import Valkey

from app.application.use_cases.limpiar_disponibilidad_pasada import LimpiarDisponibilidadPasada
from app.config import get_settings
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.disponibilidad_dia import DisponibilidadDia
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.entities.reserva_proyeccion import (
    EventoReserva,
    ReservaProyeccion,
    TipoEventoReserva,
)
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.main import create_app

pytestmark = pytest.mark.integration

AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
DIA = date(2026, 11, 5)
ENTIDAD = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Entidad"}
TURISTA = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Turista"}
EN_MINCA = Coordenada(lat=11.1426, lon=-74.1178)
EN_TAYRONA = Coordenada(lat=11.30, lon=-74.00)


def en_la_base(
    url: str, operacion: Callable[[async_sessionmaker[AsyncSession]], Awaitable[Any]]
) -> Any:
    async def correr() -> Any:
        engine = build_engine(url)
        try:
            return await operacion(build_session_factory(engine))
        finally:
            await engine.dispose()

    return asyncio.run(correr())


def servicio(
    perfil: PrestadorPerfil, nombre: str, donde: Coordenada, aforo: int
) -> AtractivoServicio:
    return AtractivoServicio.registrar(
        perfil,
        DatosServicio(
            nombre=TextoTraducido(es=nombre, en=f"{nombre} (en)"),
            descripcion=TextoTraducido(es="Entrada"),
            tipo=TipoServicio.RESERVA_PARQUE,
            ubicacion=donde,
            tarifa_base=Tarifa(Decimal("10000")),
            unidad_tarifa=UnidadTarifa.POR_PERSONA,
            capacidad_aforo_diario=aforo,
            atributos=AtributosServicio(entrada=BloqueEntrada()),
        ),
        "https://s3/",
        AHORA,
    )


def reservar(url: str, s: AtractivoServicio, personas: int, minutos: int = 0) -> None:
    reserva = ReservaProyeccion.desde_evento(
        EventoReserva(
            tipo=TipoEventoReserva.CONFIRMADA,
            reserva_id=uuid4(),
            servicio_id=s.id,
            prestador_id=s.prestador_id,
            turista_id=uuid4(),
            fecha_reserva=DIA,
            numero_personas=personas,
            ocurrido_en=AHORA + timedelta(minutes=minutos),
        )
    )

    async def guardar(sesiones: async_sessionmaker[AsyncSession]) -> None:
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.reservas.guardar(reserva)
            await uow.confirmar()

    en_la_base(url, guardar)


@pytest.fixture
def cliente(database_url: str, valkey_url: str, engine: object) -> Iterator[TestClient]:
    # La caché de capacidad es compartida entre pruebas: cada una empieza sin nada guardado.
    Valkey.from_url(valkey_url).flushdb()
    settings = get_settings().model_copy(
        update={"database_url": database_url, "valkey_url": valkey_url}
    )
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def servicios(database_url: str, cliente: TestClient) -> dict[str, AtractivoServicio]:
    """Minca: 10 de 50 personas (0,2). Tayrona: 90 de 100 (0,9, bandera)."""
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Sierra Viva")
    creados = {
        "pozo": servicio(perfil, "Pozo Azul", EN_MINCA, 50),
        "cabo": servicio(perfil, "Cabo San Juan", EN_TAYRONA, 100),
    }

    async def guardar(sesiones: async_sessionmaker[AsyncSession]) -> None:
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.prestadores.guardar(perfil)
            for s in creados.values():
                s.asignar_zona(await uow.zonas.zona_de(s.datos.ubicacion))
                await uow.servicios.guardar(s)
            await uow.confirmar()

    en_la_base(database_url, guardar)
    reservar(database_url, creados["pozo"], 10)
    reservar(database_url, creados["cabo"], 90)
    return creados


def capacidad(cliente: TestClient, cabeceras: dict, **params: Any) -> Any:
    return cliente.get(
        "/api/catalog/analitica/capacidad",
        params={"fecha": DIA.isoformat()} | params,
        headers=cabeceras,
    )


def test_la_entidad_ve_el_detalle_ordenado_por_presion(
    cliente: TestClient, servicios: dict
) -> None:
    r = capacidad(cliente, ENTIDAD)
    assert r.status_code == 200 and r.headers["content-language"] == "es"
    tayrona, minca = r.json()
    assert tayrona["zona"]["codigo"] == "parque-tayrona"
    assert (tayrona["personas_activas"], tayrona["capacidad"], tayrona["indice"]) == (90, 100, 0.9)
    assert (tayrona["nivel"], tayrona["nivel_etiqueta"]) == ("ALTO", "Alto")
    assert [b["nombre"] for b in tayrona["servicios_con_bandera"]] == ["Cabo San Juan"]
    assert (minca["zona"]["codigo"], minca["indice"], minca["nivel"]) == ("minca", 0.2, "BAJO")
    assert minca["servicios_con_bandera"] == [] and "calculado_en" in minca


def test_el_turista_solo_ve_el_nivel(cliente: TestClient, servicios: dict) -> None:
    r = capacidad(cliente, TURISTA | {"Accept-Language": "en"}, zona="parque-tayrona")
    assert r.json() == [
        {
            "zona": {"codigo": "parque-tayrona", "nombre": "Tayrona National Natural Park"},
            "fecha": DIA.isoformat(),
            "nivel": "ALTO",
            "nivel_etiqueta": "High",
        }
    ]


def test_roles_y_zona_inexistente(cliente: TestClient, servicios: dict) -> None:
    prestador = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Prestador"}
    assert capacidad(cliente, prestador).status_code == 403
    assert capacidad(cliente, ENTIDAD, zona="no-existe").status_code == 404
    assert capacidad(cliente, ENTIDAD, zona="taganga").json() == []  # sin servicios


def test_el_dato_se_cachea_cinco_minutos(
    cliente: TestClient, servicios: dict, database_url: str
) -> None:
    antes = capacidad(cliente, ENTIDAD, zona="minca").json()[0]
    reservar(database_url, servicios["pozo"], 20, minutos=1)
    despues = capacidad(cliente, ENTIDAD, zona="minca").json()[0]
    # Sale de la caché: mismo dato y misma hora de cálculo.
    assert (despues["personas_activas"], despues["calculado_en"]) == (
        antes["personas_activas"],
        antes["calculado_en"],
    )


def test_mapa_de_calor(cliente: TestClient, servicios: dict) -> None:
    r = cliente.get(
        "/api/catalog/analitica/mapa-calor", params={"fecha": DIA.isoformat()}, headers=ENTIDAD
    )
    assert r.status_code == 200 and r.headers["content-type"] == "application/geo+json"
    propiedades = {f["properties"]["codigo"]: f["properties"] for f in r.json()["features"]}
    assert (propiedades["parque-tayrona"]["indice"], propiedades["parque-tayrona"]["nivel"]) == (
        0.9,
        "ALTO",
    )
    assert propiedades["minca"]["nivel"] == "BAJO"
    assert propiedades["taganga"]["indice"] is None  # sin servicios
    assert r.json()["features"][0]["geometry"]["type"] == "MultiPolygon"
    assert cliente.get("/api/catalog/analitica/mapa-calor", headers=TURISTA).status_code == 403


async def test_limpieza_de_la_disponibilidad_pasada(sesiones: async_sessionmaker) -> None:
    hoy = date(2026, 11, 5)

    class RelojFijo:
        def ahora(self) -> datetime:
            return AHORA

        def hoy(self) -> date:
            return hoy

    servicio_id = uuid4()
    async with SqlUnidadDeTrabajo(sesiones) as uow:
        for dias in (-3, -1, 0, 2):
            await uow.disponibilidad.guardar(
                DisponibilidadDia(
                    servicio_id=servicio_id,
                    fecha=hoy + timedelta(days=dias),
                    cupos_totales=5,
                    cupos_disponibles=5,
                    version=1,
                )
            )
        await uow.confirmar()
    limpiar = LimpiarDisponibilidadPasada(lambda: SqlUnidadDeTrabajo(sesiones), RelojFijo())
    assert await limpiar.execute() == 2
    assert await limpiar.execute() == 0  # repetirla no hace daño
    async with sesiones() as session:
        fechas = list(
            await session.scalars(
                text("SELECT fecha FROM disponibilidad_proyeccion ORDER BY fecha")
            )
        )
    assert fechas == [hoy, hoy + timedelta(days=2)]
