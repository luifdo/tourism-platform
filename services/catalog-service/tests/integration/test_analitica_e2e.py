"""Analítica (UC22, UC23, UC25) completa con datos armados a mano: cada número se verifica.

Noviembre de 2026, por fecha de la visita:

| Servicio (zona, aforo)   | Reservas                                                         |
|--------------------------|------------------------------------------------------------------|
| Pozo Azul (minca, 10)    | 2 nov FINALIZADA 4 · 3 nov FINALIZADA 8 · 3 nov CANCELADA 3 ·      |
|                          | 9 nov CONFIRMADA 5 · 10 nov SOLICITADA 2 · 1 dic RECHAZADA 6 (fuera)|
| Restaurante (minca, 20)  | 4 nov CONFIRMADA 10                                              |
| Playa Grande (taganga,50)| 5 nov SOLICITADA 30 (otro prestador)                             |
"""

import asyncio
import csv
import io
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

from app.config import get_settings
from app.domain.entities.alerta_oficial import AlertaOficial
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.calificacion_resena import CalificacionResena
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.entities.reserva_proyeccion import (
    EventoReserva,
    ReservaProyeccion,
    TipoEventoReserva,
)
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.atributos.bloque_gastronomia import BloqueGastronomia
from app.domain.value_objects.atributos.valores import TipoCocina
from app.domain.value_objects.catalogos import NivelAlerta, UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.main import create_app

pytestmark = pytest.mark.integration

AHORA = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
NOVIEMBRE = {"desde": "2026-11-01", "hasta": "2026-11-30"}
ENTIDAD = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Entidad"}
T = TipoEventoReserva


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
    perfil: PrestadorPerfil, nombre: str, lat: float, lon: float, aforo: int, tipo: TipoServicio
) -> AtractivoServicio:
    atributos = (
        AtributosServicio(gastronomia=BloqueGastronomia(tipos_cocina=(TipoCocina.DE_MAR,)))
        if tipo is TipoServicio.RESTAURANTE
        else AtributosServicio(entrada=BloqueEntrada())
    )
    return AtractivoServicio.registrar(
        perfil,
        DatosServicio(
            nombre=TextoTraducido(es=nombre, en=f"{nombre} (en)"),
            descripcion=TextoTraducido(es="Descripción"),
            tipo=tipo,
            ubicacion=Coordenada(lat=lat, lon=lon),
            tarifa_base=Tarifa(Decimal("10000")),
            unidad_tarifa=UnidadTarifa.POR_PERSONA,
            capacidad_aforo_diario=aforo,
            atributos=atributos,
        ),
        "https://s3/",
        AHORA,
    )


def reserva(
    s: AtractivoServicio, dia: date, tipo: TipoEventoReserva, personas: int
) -> ReservaProyeccion:
    return ReservaProyeccion.desde_evento(
        EventoReserva(
            tipo=tipo,
            reserva_id=uuid4(),
            servicio_id=s.id,
            prestador_id=s.prestador_id,
            turista_id=uuid4(),
            fecha_reserva=dia,
            numero_personas=personas,
            ocurrido_en=AHORA,
        )
    )


@pytest.fixture
def cliente(database_url: str, valkey_url: str, engine: object) -> Iterator[TestClient]:
    Valkey.from_url(valkey_url).flushdb()
    settings = get_settings().model_copy(
        update={"database_url": database_url, "valkey_url": valkey_url}
    )
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def datos(database_url: str, cliente: TestClient) -> dict[str, Any]:
    sierra = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Sierra Viva")
    otro = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Playa Linda")
    pozo = servicio(sierra, "Pozo Azul", 11.1426, -74.1178, 10, TipoServicio.RESERVA_PARQUE)
    restaurante = servicio(sierra, "Restaurante", 11.1450, -74.1150, 20, TipoServicio.RESTAURANTE)
    playa = servicio(otro, "Playa Grande", 11.2650, -74.1900, 50, TipoServicio.ACCESO_PLAYA)
    reservas = [
        reserva(pozo, date(2026, 11, 2), T.FINALIZADA, 4),
        reserva(pozo, date(2026, 11, 3), T.FINALIZADA, 8),
        reserva(pozo, date(2026, 11, 3), T.CANCELADA, 3),
        reserva(pozo, date(2026, 11, 9), T.CONFIRMADA, 5),
        reserva(pozo, date(2026, 11, 10), T.SOLICITADA, 2),
        reserva(pozo, date(2026, 12, 1), T.RECHAZADA, 6),  # fuera de noviembre
        reserva(restaurante, date(2026, 11, 4), T.CONFIRMADA, 10),
        reserva(playa, date(2026, 11, 5), T.SOLICITADA, 30),
    ]

    async def guardar(sesiones: async_sessionmaker[AsyncSession]) -> None:
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            for perfil in (sierra, otro):
                await uow.prestadores.guardar(perfil)
            for s in (pozo, restaurante, playa):
                s.asignar_zona(await uow.zonas.zona_de(s.datos.ubicacion))
                await uow.servicios.guardar(s)
            for r in reservas:
                await uow.reservas.guardar(r)
            for puntuacion, visible in ((5, True), (3, True), (1, False)):  # la de 1, oculta
                await uow.calificaciones.guardar(
                    CalificacionResena.desde_evento(uuid4(), pozo.id, puntuacion, visible, AHORA)
                )
            await uow.alertas.guardar(
                AlertaOficial.publicar(
                    nivel=NivelAlerta.PREVENTIVA,
                    mensaje=TextoTraducido(es="Sendero cerrado"),
                    entidad_usuario_id=uuid4(),
                    fecha_expiracion=datetime.now(UTC) + timedelta(days=2),
                    ahora=datetime.now(UTC),
                    servicio_id=pozo.id,
                )
            )
            await uow.confirmar()
        async with sesiones() as session, session.begin():
            for servicio_id, dia, conteo in (
                (pozo.id, date(2026, 11, 2), 3),
                (playa.id, date(2026, 11, 5), 2),
            ):
                await session.execute(
                    text("INSERT INTO intencion_visita_dia VALUES (:s, :d, :c)"),
                    {"s": servicio_id, "d": dia, "c": conteo},
                )

    en_la_base(database_url, guardar)
    return {
        "sierra": {"X-Usuario-Id": str(sierra.usuario_id), "X-Usuario-Rol": "Prestador"},
        "pozo": pozo,
        "restaurante": restaurante,
    }


def test_metricas_del_prestador(cliente: TestClient, datos: dict) -> None:
    r = cliente.get("/api/catalog/prestador/metricas", params=NOVIEMBRE, headers=datos["sierra"])
    assert r.status_code == 200
    cuerpo = r.json()
    assert (cuerpo["desde"], cuerpo["hasta"]) == ("2026-11-01", "2026-11-30")
    pozo, restaurante = cuerpo["servicios"]  # solo los suyos, por nombre
    assert pozo["nombre"] == "Pozo Azul"
    assert pozo["reservas"] == {
        "solicitadas": 1,
        "confirmadas": 1,
        "rechazadas": 0,  # la de diciembre queda fuera del rango
        "canceladas": 1,
        "finalizadas": 2,
    }
    assert pozo["personas_finalizadas"] == 12
    assert pozo["ocupacion"] == 0.04  # 12 ÷ (10 × 30 días)
    assert (pozo["calificacion_promedio"], pozo["total_resenas"]) == (4.0, 2)  # sin la oculta
    assert pozo["intenciones_visita"] == 3
    assert restaurante["reservas"]["confirmadas"] == 1 and restaurante["ocupacion"] == 0
    assert restaurante["calificacion_promedio"] is None

    assert (
        cliente.get(
            "/api/catalog/prestador/metricas", params=NOVIEMBRE, headers=ENTIDAD
        ).status_code
        == 403
    )


def test_demanda_por_semana_zona_y_categoria(cliente: TestClient, datos: dict) -> None:
    def serie(**extra: str) -> list[dict]:
        r = cliente.get(
            "/api/catalog/analitica/demanda",
            params=NOVIEMBRE | {"agrupacion": "semana"} | extra,
            headers=ENTIDAD,
        )
        assert r.status_code == 200, r.text
        return r.json()["serie"]

    total = serie()
    # 1 de noviembre es domingo: la primera semana empieza el lunes 26 de octubre.
    assert [p["periodo"] for p in total] == [
        "2026-10-26",
        "2026-11-02",
        "2026-11-09",
        "2026-11-16",
        "2026-11-23",
        "2026-11-30",
    ]
    semana_2 = total[1]
    assert (
        semana_2["personas_solicitadas"],
        semana_2["personas_confirmadas"],
        semana_2["personas_finalizadas"],
        semana_2["personas_canceladas"],
    ) == (30, 10, 12, 3)
    assert (total[2]["personas_confirmadas"], total[2]["personas_solicitadas"]) == (5, 2)
    assert total[0]["personas_solicitadas"] == 0 and total[0]["zona"] is None  # sin huecos

    minca = serie(zona="minca")[1]
    assert (minca["zona"], minca["personas_solicitadas"], minca["personas_confirmadas"]) == (
        "minca",
        0,
        10,
    )
    restaurantes = serie(categoria="GASTRONOMIA")[1]
    assert (restaurantes["personas_confirmadas"], restaurantes["personas_finalizadas"]) == (10, 0)

    [mes] = cliente.get(
        "/api/catalog/analitica/demanda",
        params=NOVIEMBRE | {"agrupacion": "mes"},
        headers=ENTIDAD,
    ).json()["serie"]
    assert (mes["periodo"], mes["personas_solicitadas"], mes["personas_confirmadas"]) == (
        "2026-11-01",
        32,
        15,
    )
    assert (
        cliente.get(
            "/api/catalog/analitica/demanda",
            params=NOVIEMBRE | {"zona": "no-existe"},
            headers=ENTIDAD,
        ).status_code
        == 404
    )


def test_tablero(cliente: TestClient, datos: dict) -> None:
    r = cliente.get("/api/catalog/analitica/tablero", params=NOVIEMBRE, headers=ENTIDAD)
    assert r.status_code == 200
    tablero = r.json()
    totales = tablero["totales"]
    assert (
        totales["periodo"],
        totales["personas_solicitadas"],
        totales["personas_confirmadas"],
        totales["personas_finalizadas"],
        totales["personas_canceladas"],
    ) == ("2026-11-01", 32, 15, 12, 3)
    assert [
        (z["zona"]["codigo"], z["personas"], z["intenciones_visita"])
        for z in tablero["zonas_mas_demandadas"]
    ] == [("taganga", 30, 2), ("minca", 29, 3)]
    assert {c["zona"]["codigo"] for c in tablero["capacidad_hoy"]} == {"minca", "taganga"}
    assert tablero["alertas_vigentes"] == 1
    turista = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Turista"}
    assert (
        cliente.get("/api/catalog/analitica/tablero", params=NOVIEMBRE, headers=turista).status_code
        == 403
    )


def test_reporte_csv_cuadra_con_el_tablero_y_se_audita(
    cliente: TestClient, datos: dict, database_url: str
) -> None:
    r = cliente.get("/api/catalog/analitica/reportes/demanda", params=NOVIEMBRE, headers=ENTIDAD)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert (
        r.headers["content-disposition"]
        == 'attachment; filename="demanda_2026-11-01_2026-11-30.csv"'
    )
    assert r.content.startswith("﻿".encode())
    encabezado, *filas = list(
        csv.reader(io.StringIO(r.content.decode("utf-8").removeprefix("﻿")), delimiter=";")
    )
    assert encabezado[0:3] == ["Fecha", "Zona", "Servicio"]
    # Una fila por servicio y día con actividad, en orden de fecha.
    assert [(f[0], f[2]) for f in filas] == [
        ("2026-11-02", "Pozo Azul"),
        ("2026-11-03", "Pozo Azul"),
        ("2026-11-04", "Restaurante"),
        ("2026-11-05", "Playa Grande"),
        ("2026-11-09", "Pozo Azul"),
        ("2026-11-10", "Pozo Azul"),
    ]
    dia_3 = filas[1]
    assert dia_3[1] == "Minca" and dia_3[3] == "Naturaleza" and dia_3[4] == "Reserva o parque"
    assert dia_3[5:13] == ["0", "0", "8", "3", "8", "10", "0,80", "0"]
    # Los totales cuadran con el tablero: 32 solicitadas, 15 confirmadas, 12 finalizadas, 3
    # canceladas.
    totales = [sum(int(f[i]) for f in filas) for i in (5, 6, 7, 8)]
    assert totales == [32, 15, 12, 3]
    assert sum(int(f[12]) for f in filas) == 5  # intenciones: 3 en Minca y 2 en Taganga

    async def acciones(sesiones: async_sessionmaker[AsyncSession]) -> list[dict]:
        async with sesiones() as session:
            return list(
                await session.scalars(
                    text(
                        "SELECT sobre->'payload' FROM outbox"
                        " WHERE sobre->'payload'->>'accion' = 'EXPORT'"
                    )
                )
            )

    [auditoria] = en_la_base(database_url, acciones)
    assert auditoria["usuario_id"] == ENTIDAD["X-Usuario-Id"]
    assert auditoria["detalles"]["desde"] == "2026-11-01"

    solo_taganga = cliente.get(
        "/api/catalog/analitica/reportes/demanda",
        params=NOVIEMBRE | {"zona": "taganga"},
        headers=ENTIDAD,
    )
    assert len(solo_taganga.content.decode("utf-8").strip().splitlines()) == 2  # encabezado + 1
    assert (
        cliente.get(
            "/api/catalog/analitica/reportes/demanda", params=NOVIEMBRE, headers=datos["sierra"]
        ).status_code
        == 403
    )
