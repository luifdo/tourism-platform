"""Mapa sobre PostGIS real: recorte por vista, agrupación por zoom, polígonos y alertas."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.criterios_mapa_servicios import CriteriosMapaServicios
from app.application.dto.escala_mapa import EscalaMapa
from app.domain.entities.alerta_oficial import AlertaOficial
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.calificacion_resena import CalificacionResena
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.atributos.bloque_gastronomia import BloqueGastronomia
from app.domain.value_objects.atributos.valores import TipoCocina
from app.domain.value_objects.catalogos import Categoria, NivelAlerta, UnidadTarifa
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.geo import Bbox, Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.persistence.consultas.sql_consulta_mapa import SqlConsultaMapa
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

pytestmark = pytest.mark.integration

Sesiones = async_sessionmaker[AsyncSession]
AHORA = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
ORIGEN = "https://s3.turismo.local/catalogo-imagenes/"
SANTA_MARTA = Bbox(min_lon=-74.30, min_lat=11.05, max_lon=-73.90, max_lat=11.40)
CENTRO = Bbox(min_lon=-74.2160, min_lat=11.2330, max_lon=-74.1960, max_lat=11.2500)

# Cinco servicios en el Centro Histórico (a pocos metros) y uno en Minca, a ~15 km.
EN_EL_CENTRO = [Coordenada(lat=11.2420 + i * 0.0003, lon=-74.2110 + i * 0.0003) for i in range(5)]
EN_MINCA = Coordenada(lat=11.1426, lon=-74.1178)


# Un tipo por categoría con su bloque principal mínimo (las pruebas filtran por categoría).
TIPO_DE = {
    Categoria.PLAYA: TipoServicio.ACCESO_PLAYA,
    Categoria.CULTURA: TipoServicio.MUSEO_SITIO,
    Categoria.NATURALEZA: TipoServicio.RESERVA_PARQUE,
    Categoria.GASTRONOMIA: TipoServicio.RESTAURANTE,
}


def atributos_de(tipo: TipoServicio) -> AtributosServicio:
    if tipo is TipoServicio.RESTAURANTE:
        return AtributosServicio(gastronomia=BloqueGastronomia(tipos_cocina=(TipoCocina.DE_MAR,)))
    return AtributosServicio(entrada=BloqueEntrada())


def servicio(
    perfil: PrestadorPerfil, nombre: str, categoria: Categoria, ubicacion: Coordenada
) -> AtractivoServicio:
    datos = DatosServicio(
        nombre=TextoTraducido(es=nombre, en=f"{nombre} (en)"),
        descripcion=TextoTraducido(es="Descripción"),
        tipo=TIPO_DE[categoria],
        unidad_tarifa=UnidadTarifa.POR_PERSONA,
        atributos=atributos_de(TIPO_DE[categoria]),
        ubicacion=ubicacion,
        tarifa_base=Tarifa(Decimal("50000")),
        capacidad_aforo_diario=20,
        imagenes_urls=(f"{ORIGEN}{uuid4()}.webp",),
    )
    return AtractivoServicio.registrar(perfil, datos, ORIGEN, AHORA)


@pytest.fixture
async def ids(sesiones: Sesiones) -> dict[str, UUID]:
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Turismo Sierra")
    del_centro = [
        servicio(perfil, f"Centro {i}", Categoria.CULTURA, c) for i, c in enumerate(EN_EL_CENTRO)
    ]
    cafe = servicio(perfil, "Tour del café", Categoria.GASTRONOMIA, EN_MINCA)
    apagado = servicio(perfil, "Apagado", Categoria.CULTURA, EN_EL_CENTRO[0])
    apagado.desactivar(perfil, 1, AHORA)
    async with SqlUnidadDeTrabajo(sesiones) as uow:
        await uow.prestadores.guardar(perfil)
        for s in (*del_centro, cafe, apagado):
            s.asignar_zona(await uow.zonas.zona_de(s.datos.ubicacion))
            await uow.servicios.guardar(s)
        await uow.calificaciones.guardar(
            CalificacionResena(resena_id=uuid4(), servicio_id=cafe.id, puntuacion=4)
        )
        await uow.calificaciones.guardar(
            CalificacionResena(resena_id=uuid4(), servicio_id=del_centro[2].id, puntuacion=5)
        )
        minca = await uow.zonas.obtener_por_codigo(CodigoZona("minca"))
        assert minca is not None
        for alerta in (
            AlertaOficial.publicar(
                NivelAlerta.PREVENTIVA,
                TextoTraducido(es="Lluvias en Minca"),
                uuid4(),
                AHORA + timedelta(days=1),
                AHORA,
                zona_id=minca.id,
            ),
            AlertaOficial.publicar(
                NivelAlerta.CRITICA,
                TextoTraducido(es="Finca cerrada"),
                uuid4(),
                AHORA + timedelta(days=1),
                AHORA,
                servicio_id=cafe.id,
            ),
            AlertaOficial.publicar(
                NivelAlerta.INFORMATIVA,
                TextoTraducido(es="De un servicio apagado"),
                uuid4(),
                AHORA + timedelta(days=1),
                AHORA,
                servicio_id=apagado.id,
            ),
        ):
            await uow.alertas.guardar(alerta)
        await uow.confirmar()
    return {"cafe": cafe.id, "centro_2": del_centro[2].id, "minca": minca.id}


def criterios(vista: Bbox, zoom: int, **filtros: object) -> CriteriosMapaServicios:
    return CriteriosMapaServicios(vista=vista, escala=EscalaMapa(zoom), **filtros)  # type: ignore[arg-type]


class TestServicios:
    async def test_zoom_bajo_agrupa_lo_cercano(self, sesiones: Sesiones, ids: dict) -> None:
        mapa = await SqlConsultaMapa(sesiones).servicios(criterios(SANTA_MARTA, 11))
        # El centro es un grupo de cinco; Minca, solo, llega como servicio con su calificación.
        assert [g.conteo for g in mapa.grupos] == [5]
        grupo = mapa.grupos[0]
        assert CENTRO.min_lat < grupo.ubicacion.lat < CENTRO.max_lat
        assert CENTRO.min_lon < grupo.ubicacion.lon < CENTRO.max_lon
        [cafe] = mapa.servicios
        assert (cafe.id, cafe.calificacion_promedio) == (ids["cafe"], 4.0)
        assert cafe.ubicacion == EN_MINCA

    async def test_zoom_alto_devuelve_cada_servicio(self, sesiones: Sesiones, ids: dict) -> None:
        mapa = await SqlConsultaMapa(sesiones).servicios(criterios(CENTRO, 15))
        assert mapa.grupos == () and len(mapa.servicios) == 5  # el apagado no aparece
        assert mapa.servicios[0].id == ids["centro_2"]  # primero el mejor calificado

    async def test_solo_lo_que_cae_en_la_vista(self, sesiones: Sesiones, ids: dict) -> None:
        consulta = SqlConsultaMapa(sesiones)
        assert len((await consulta.servicios(criterios(CENTRO, 14))).servicios) == 5
        lejos = Bbox(min_lon=-73.5, min_lat=10.5, max_lon=-73.4, max_lat=10.6)
        assert await consulta.servicios(criterios(lejos, 14)) == await consulta.servicios(
            criterios(lejos, 8)
        )
        assert (await consulta.servicios(criterios(lejos, 14))).servicios == ()

    async def test_filtros_por_categoria_y_zona(self, sesiones: Sesiones, ids: dict) -> None:
        consulta = SqlConsultaMapa(sesiones)
        gastronomia = await consulta.servicios(
            criterios(SANTA_MARTA, 16, categorias=(Categoria.GASTRONOMIA,))
        )
        assert [s.id for s in gastronomia.servicios] == [ids["cafe"]]
        en_minca = await consulta.servicios(criterios(SANTA_MARTA, 10, zona="minca"))
        assert [s.id for s in en_minca.servicios] == [ids["cafe"]] and en_minca.grupos == ()

    async def test_el_recorte_usa_el_indice_del_mapa(self, sesiones: Sesiones) -> None:
        async with sesiones() as session:
            await session.execute(text("SET LOCAL enable_seqscan = off"))
            plan = "\n".join(
                (
                    await session.execute(
                        text(
                            "EXPLAIN SELECT id FROM atractivo_servicio s WHERE s.activo AND "
                            "s.ubicacion::geometry && "
                            "ST_MakeEnvelope(-74.3, 11.0, -73.9, 11.4, 4326)"
                        )
                    )
                ).scalars()
            )
        assert "ix_servicio_ubicacion_plana" in plan


class TestZonas:
    async def test_poligonos_en_lon_lat_recortados_por_vista(self, sesiones: Sesiones) -> None:
        consulta = SqlConsultaMapa(sesiones)
        todas = await consulta.zonas(None, EscalaMapa(12))
        assert len(todas) == 6
        assert {z.geometria["type"] for z in todas} == {"MultiPolygon"}
        en_el_centro = await consulta.zonas(CENTRO, EscalaMapa(12))
        assert [z.codigo for z in en_el_centro] == ["centro-historico"]
        lon, lat = en_el_centro[0].geometria["coordinates"][0][0][0]
        assert (CENTRO.min_lon, CENTRO.min_lat) <= (lon, lat)  # [lon, lat], no al revés
        assert -75 < lon < -73 and 11 < lat < 12

    async def test_zoom_bajo_simplifica_y_nunca_deja_la_zona_vacia(
        self, sesiones: Sesiones
    ) -> None:
        async with sesiones.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO zona (id, codigo, nombre, poligono, activa) VALUES "
                    "(:id, 'prueba-circulo', '{\"es\": \"Círculo\"}', "
                    "ST_Multi(ST_Buffer(ST_SetSRID(ST_MakePoint(-74.0, 11.5), 4326), 0.01, 64)), "
                    "true)"
                ),
                {"id": uuid4()},
            )

        def vertices(zonas: list) -> int:
            [circulo] = [z for z in zonas if z.codigo == "prueba-circulo"]
            return sum(
                len(anillo) for poligono in circulo.geometria["coordinates"] for anillo in poligono
            )

        consulta = SqlConsultaMapa(sesiones)
        cerca = vertices(await consulta.zonas(None, EscalaMapa(18)))
        lejos = vertices(await consulta.zonas(None, EscalaMapa(8)))
        # El círculo tiene 257 vértices: de cerca se conserva casi entero, de lejos queda en unos
        # pocos (sin desaparecer: un anillo necesita al menos 4).
        assert cerca > 100 and 4 <= lejos < cerca / 5


class TestAlertas:
    async def test_punto_del_servicio_y_poligono_de_la_zona(
        self, sesiones: Sesiones, ids: dict
    ) -> None:
        alertas = await SqlConsultaMapa(sesiones).alertas(AHORA, SANTA_MARTA)
        # La del servicio apagado no se dibuja: no tiene dónde.
        assert [a.alerta.nivel for a in alertas] == [NivelAlerta.CRITICA, NivelAlerta.PREVENTIVA]
        punto, poligono = (a.geometria for a in alertas)
        assert punto == {"type": "Point", "coordinates": [EN_MINCA.lon, EN_MINCA.lat]}
        assert poligono["type"] == "MultiPolygon"

    async def test_recorte_por_vista_y_vencimiento(self, sesiones: Sesiones, ids: dict) -> None:
        consulta = SqlConsultaMapa(sesiones)
        assert await consulta.alertas(AHORA, CENTRO) == []
        assert await consulta.alertas(AHORA + timedelta(days=2), None) == []
