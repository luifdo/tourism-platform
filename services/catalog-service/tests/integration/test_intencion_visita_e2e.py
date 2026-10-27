"""Intención de visita ("Cómo llegar") completa: HTTP → Valkey (descarte) → PostGIS (conteo)."""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from valkey import Valkey

from app.config import get_settings
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.infrastructure.reloj import RelojSistema
from app.main import create_app

pytestmark = pytest.mark.integration

ENTIDAD = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Entidad"}
AHORA = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)


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


@pytest.fixture
def cliente(database_url: str, valkey_url: str, engine: object) -> Iterator[TestClient]:
    Valkey.from_url(valkey_url).flushdb()  # las marcas de visitantes no pasan de una prueba a otra
    settings = get_settings().model_copy(
        update={"database_url": database_url, "valkey_url": valkey_url}
    )
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def servicios(database_url: str, cliente: TestClient) -> dict[str, AtractivoServicio]:
    """Dos servicios en Minca y uno en Taganga; uno de Minca está apagado."""
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Sierra Viva")

    def nuevo(nombre: str, lat: float, lon: float) -> AtractivoServicio:
        return AtractivoServicio.registrar(
            perfil,
            DatosServicio(
                nombre=TextoTraducido(es=nombre),
                descripcion=TextoTraducido(es="Entrada"),
                tipo=TipoServicio.RESERVA_PARQUE,
                ubicacion=Coordenada(lat=lat, lon=lon),
                tarifa_base=Tarifa(Decimal("10000")),
                unidad_tarifa=UnidadTarifa.POR_PERSONA,
                capacidad_aforo_diario=50,
                atributos=AtributosServicio(entrada=BloqueEntrada()),
            ),
            "https://s3/",
            AHORA,
        )

    creados = {
        "pozo": nuevo("Pozo Azul", 11.1426, -74.1178),
        "cafe": nuevo("Finca de café", 11.1450, -74.1150),
        "playa": nuevo("Playa Grande", 11.2650, -74.1900),
        "apagado": nuevo("Mirador cerrado", 11.1430, -74.1170),
    }
    creados["apagado"].desactivar(perfil, 1, AHORA)

    async def guardar(sesiones: async_sessionmaker[AsyncSession]) -> None:
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.prestadores.guardar(perfil)
            for s in creados.values():
                s.asignar_zona(await uow.zonas.zona_de(s.datos.ubicacion))
                await uow.servicios.guardar(s)
            await uow.confirmar()

    en_la_base(database_url, guardar)
    return creados


def como_llegar(cliente: TestClient, servicio_id: Any, ip: str) -> int:
    r = cliente.post(
        f"/api/catalog/servicios/{servicio_id}/intencion-visita",
        headers={"X-Forwarded-For": f"{ip}, 10.42.0.3"},
    )
    return r.status_code


def conteos(url: str) -> dict[str, int]:
    async def leer(sesiones: async_sessionmaker[AsyncSession]) -> dict[str, int]:
        async with sesiones() as session:
            filas = await session.execute(
                text("SELECT servicio_id::text, conteo FROM intencion_visita_dia")
            )
            return {f[0]: f[1] for f in filas}

    return en_la_base(url, leer)


def test_una_vez_por_visitante_servicio_y_dia(
    cliente: TestClient, servicios: dict, database_url: str
) -> None:
    pozo = servicios["pozo"].id
    assert como_llegar(cliente, pozo, "190.24.1.7") == 204
    assert como_llegar(cliente, pozo, "190.24.1.7") == 204  # el mismo vuelve a pedirla
    assert como_llegar(cliente, pozo, "181.50.3.9") == 204  # otro visitante
    assert como_llegar(cliente, servicios["cafe"].id, "190.24.1.7") == 204  # otro servicio
    assert conteos(database_url) == {str(pozo): 2, str(servicios["cafe"].id): 1}


def test_el_ip_no_se_guarda(cliente: TestClient, servicios: dict, valkey_url: str) -> None:
    como_llegar(cliente, servicios["pozo"].id, "190.24.1.7")
    claves = [k.decode() for k in Valkey.from_url(valkey_url).keys("catalog:intencion:*")]
    assert len(claves) == 1 and "190.24.1.7" not in claves[0]
    assert Valkey.from_url(valkey_url).ttl(claves[0]) > 23 * 3600  # dura 24 h


def test_servicio_apagado_o_inexistente_es_404_sin_contar(
    cliente: TestClient, servicios: dict, database_url: str
) -> None:
    assert como_llegar(cliente, servicios["apagado"].id, "190.24.1.7") == 404
    assert como_llegar(cliente, servicios["apagado"].id, "190.24.1.7") == 404  # no quedó marca
    assert como_llegar(cliente, uuid4(), "190.24.1.7") == 404
    assert conteos(database_url) == {}


def test_la_entidad_ve_los_conteos_por_zona_y_dia(cliente: TestClient, servicios: dict) -> None:
    for ip in ("190.24.1.7", "181.50.3.9"):
        como_llegar(cliente, servicios["pozo"].id, ip)
    como_llegar(cliente, servicios["cafe"].id, "190.24.1.7")
    como_llegar(cliente, servicios["playa"].id, "190.24.1.7")
    hoy = RelojSistema().hoy().isoformat()
    r = cliente.get(
        "/api/catalog/analitica/intenciones-visita",
        params={"desde": hoy, "hasta": hoy},
        headers=ENTIDAD,
    )
    assert r.status_code == 200
    por_zona = {f["zona"]: f["intenciones"] for f in r.json()}
    assert por_zona == {"minca": 3, "taganga": 1}
    solo_minca = cliente.get(
        "/api/catalog/analitica/intenciones-visita",
        params={"desde": hoy, "hasta": hoy, "zona": "minca"},
        headers=ENTIDAD,
    ).json()
    assert solo_minca == [{"zona": "minca", "fecha": hoy, "intenciones": 3}]


def test_roles_y_rango(cliente: TestClient) -> None:
    turista = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Turista"}
    params = {"desde": "2026-10-01", "hasta": "2026-10-31"}
    ruta = "/api/catalog/analitica/intenciones-visita"
    assert cliente.get(ruta, params=params, headers=turista).status_code == 403
    invertido = {"desde": "2026-10-31", "hasta": "2026-10-01"}
    assert cliente.get(ruta, params=invertido, headers=ENTIDAD).status_code == 400
    largo = {"desde": "2025-01-01", "hasta": "2026-10-01"}
    assert cliente.get(ruta, params=largo, headers=ENTIDAD).status_code == 400
