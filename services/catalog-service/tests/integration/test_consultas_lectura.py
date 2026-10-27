"""Consultas de lectura sobre PostGIS real: filtros, distancia, texto, paginación y alertas."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.criterios_busqueda import CriteriosBusqueda, OrdenBusqueda
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
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.persistence.consultas.sql_consulta_alertas import SqlConsultaAlertas
from app.infrastructure.persistence.consultas.sql_consulta_servicios import SqlConsultaServicios
from app.infrastructure.persistence.consultas.sql_consulta_zonas import SqlConsultaZonas
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

pytestmark = pytest.mark.integration

Sesiones = async_sessionmaker[AsyncSession]
AHORA = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
ORIGEN = "https://s3.turismo.local/catalogo-imagenes/"
CENTRO = Coordenada(lat=11.2420, lon=-74.2110)


@dataclass
class Datos:
    cafe: UUID
    playa: UUID
    museo: UUID
    apagado: UUID


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
    perfil: PrestadorPerfil,
    nombre: TextoTraducido,
    descripcion: str,
    categoria: Categoria,
    ubicacion: Coordenada,
    tarifa: str,
) -> AtractivoServicio:
    datos = DatosServicio(
        nombre=nombre,
        descripcion=TextoTraducido(es=descripcion),
        tipo=TIPO_DE[categoria],
        unidad_tarifa=UnidadTarifa.POR_PERSONA,
        atributos=atributos_de(TIPO_DE[categoria]),
        ubicacion=ubicacion,
        tarifa_base=Tarifa(Decimal(tarifa)),
        capacidad_aforo_diario=20,
        imagenes_urls=(f"{ORIGEN}{uuid4()}.webp",),
    )
    return AtractivoServicio.registrar(perfil, datos, ORIGEN, AHORA)


@pytest.fixture
async def datos(sesiones: Sesiones) -> Datos:
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Turismo Sierra")
    perfil.editar(
        1, "3001234567", None, TextoTraducido(es="Gratis 24 h antes", en="Free 24 h before")
    )
    cafe = servicio(
        perfil,
        TextoTraducido(es="Tour del café", en="Coffee tour"),
        "Recorrido por fincas cafeteras de Minca",
        Categoria.GASTRONOMIA,
        Coordenada(lat=11.1426, lon=-74.1178),
        "85000",
    )
    playa = servicio(
        perfil,
        TextoTraducido(es="Playa Grande en lancha"),  # sin inglés: se busca con su español
        "Paseo en lancha desde Taganga",
        Categoria.PLAYA,
        Coordenada(lat=11.2650, lon=-74.1900),
        "60000",
    )
    museo = servicio(
        perfil,
        TextoTraducido(es="Museo del Oro Tairona", en="Tairona Gold Museum"),
        "Historia precolombina en el centro",
        Categoria.CULTURA,
        Coordenada(lat=11.2425, lon=-74.2118),  # a unos 90 m de CENTRO
        "0",
    )
    apagado = servicio(
        perfil,
        TextoTraducido(es="Café cerrado"),
        "No debe aparecer",
        Categoria.GASTRONOMIA,
        Coordenada(lat=11.2421, lon=-74.2111),
        "10000",
    )
    apagado.desactivar(perfil, 1, AHORA)

    async with SqlUnidadDeTrabajo(sesiones) as uow:
        await uow.prestadores.guardar(perfil)
        for s in (cafe, playa, museo, apagado):
            s.asignar_zona(await uow.zonas.zona_de(s.datos.ubicacion))
            await uow.servicios.guardar(s)
        for puntuacion in (5, 4):
            await uow.calificaciones.guardar(
                CalificacionResena(resena_id=uuid4(), servicio_id=museo.id, puntuacion=puntuacion)
            )
        await uow.calificaciones.guardar(
            CalificacionResena(resena_id=uuid4(), servicio_id=cafe.id, puntuacion=3)
        )
        minca = await uow.zonas.obtener_por_codigo(CodigoZona("minca"))
        assert minca is not None
        alertas = [
            AlertaOficial.publicar(
                NivelAlerta.PREVENTIVA,
                TextoTraducido(es="Lluvias en Minca"),
                uuid4(),
                AHORA + timedelta(days=2),
                AHORA,
                zona_id=minca.id,
            ),
            AlertaOficial.publicar(
                NivelAlerta.CRITICA,
                TextoTraducido(es="Finca cerrada hoy"),
                uuid4(),
                AHORA + timedelta(days=1),
                AHORA,
                servicio_id=cafe.id,
            ),
            AlertaOficial.publicar(
                NivelAlerta.INFORMATIVA,
                TextoTraducido(es="Ya venció"),
                uuid4(),
                AHORA + timedelta(hours=1),
                AHORA,
                zona_id=minca.id,
            ),
        ]
        for alerta in alertas:
            await uow.alertas.guardar(alerta)
        await uow.confirmar()
    return Datos(cafe=cafe.id, playa=playa.id, museo=museo.id, apagado=apagado.id)


def ids(pagina) -> list[UUID]:  # noqa: ANN001
    return [s.id for s in pagina.items]


class TestBuscar:
    async def test_solo_activos_y_orden_por_calificacion(
        self, sesiones: Sesiones, datos: Datos
    ) -> None:
        pagina = await SqlConsultaServicios(sesiones).buscar(CriteriosBusqueda(idioma=Idioma.ES))
        assert ids(pagina) == [datos.museo, datos.cafe, datos.playa]  # 4,5 > 3 > sin reseñas
        assert pagina.total == 3
        museo = pagina.items[0]
        assert (museo.calificacion_promedio, museo.total_resenas) == (4.5, 2)
        assert museo.zona is not None and museo.zona.codigo == "centro-historico"
        assert museo.imagen_principal and museo.imagen_principal.startswith(ORIGEN)

    async def test_filtros_combinados(self, sesiones: Sesiones, datos: Datos) -> None:
        consulta = SqlConsultaServicios(sesiones)
        assert ids(await consulta.buscar(CriteriosBusqueda(idioma=Idioma.ES, zona="minca"))) == [
            datos.cafe
        ]
        por_precio = CriteriosBusqueda(
            idioma=Idioma.ES, precio_min=Decimal("1"), precio_max=Decimal("70000")
        )
        assert ids(await consulta.buscar(por_precio)) == [datos.playa]
        varias = CriteriosBusqueda(
            idioma=Idioma.ES,
            categorias=(Categoria.PLAYA, Categoria.CULTURA),
            orden=OrdenBusqueda.PRECIO,
        )
        assert ids(await consulta.buscar(varias)) == [datos.museo, datos.playa]

    async def test_cercania_en_metros(self, sesiones: Sesiones, datos: Datos) -> None:
        criterios = CriteriosBusqueda(
            idioma=Idioma.ES, cerca_de=CENTRO, radio_m=6000, orden=OrdenBusqueda.DISTANCIA
        )
        pagina = await SqlConsultaServicios(sesiones).buscar(criterios)
        assert ids(pagina) == [datos.museo, datos.playa]  # Minca queda a más de 6 km
        assert pagina.items[0].distancia_m is not None and 80 < pagina.items[0].distancia_m < 110
        assert pagina.items[1].distancia_m is not None and pagina.items[1].distancia_m > 2000

    @pytest.mark.parametrize(
        ("idioma", "texto", "esperado"),
        [
            (Idioma.ES, "cafe", "cafe"),  # sin tilde encuentra «café»
            (Idioma.ES, "cafeteras", "cafe"),
            (Idioma.EN, "coffee", "cafe"),
            (Idioma.EN, "lancha", "playa"),  # sin traducción, se busca en su español
            (Idioma.ES, '"museo del oro"', "museo"),
        ],
    )
    async def test_texto_por_idioma(
        self, sesiones: Sesiones, datos: Datos, idioma: Idioma, texto: str, esperado: str
    ) -> None:
        criterios = CriteriosBusqueda(idioma=idioma, texto=texto, orden=OrdenBusqueda.RELEVANCIA)
        assert ids(await SqlConsultaServicios(sesiones).buscar(criterios)) == [
            getattr(datos, esperado)
        ]

    async def test_paginacion(self, sesiones: Sesiones, datos: Datos) -> None:
        consulta = SqlConsultaServicios(sesiones)
        segunda = await consulta.buscar(CriteriosBusqueda(idioma=Idioma.ES, pagina=2, tamano=2))
        assert ids(segunda) == [datos.playa] and segunda.total == 3
        fuera = await consulta.buscar(CriteriosBusqueda(idioma=Idioma.ES, pagina=9, tamano=2))
        assert fuera.items == () and fuera.total == 3


class TestDetalle:
    async def test_ficha_con_alertas_del_servicio_y_de_su_zona(
        self, sesiones: Sesiones, datos: Datos
    ) -> None:
        detalle = await SqlConsultaServicios(sesiones).detalle(
            datos.cafe, AHORA + timedelta(hours=2)
        )
        assert detalle is not None
        assert detalle.prestador.razon_social == "Turismo Sierra"
        assert detalle.prestador.politica_cancelacion == TextoTraducido(
            es="Gratis 24 h antes", en="Free 24 h before"
        )
        # La crítica primero; la que venció no aparece.
        assert [a.mensaje.es for a in detalle.alertas] == ["Finca cerrada hoy", "Lluvias en Minca"]

    async def test_inactivo_no_tiene_ficha(self, sesiones: Sesiones, datos: Datos) -> None:
        assert await SqlConsultaServicios(sesiones).detalle(datos.apagado, AHORA) is None


class TestZonasYAlertas:
    async def test_centro_cae_dentro_de_cada_zona(self, sesiones: Sesiones) -> None:
        zonas = await SqlConsultaZonas(sesiones).activas()
        assert len(zonas) == 6
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            for zona in zonas:
                assert await uow.zonas.zona_de(zona.centro) == zona.id

    async def test_alertas_por_zona_incluyen_las_de_sus_servicios(
        self, sesiones: Sesiones, datos: Datos
    ) -> None:
        consulta = SqlConsultaAlertas(sesiones)
        en_minca = await consulta.vigentes(AHORA, zona="minca")
        assert [a.nivel for a in en_minca] == [
            NivelAlerta.CRITICA,
            NivelAlerta.PREVENTIVA,
            NivelAlerta.INFORMATIVA,
        ]
        assert await consulta.vigentes(AHORA, zona="taganga") == []
        mas_tarde = await consulta.vigentes(AHORA + timedelta(hours=2))
        assert len(mas_tarde) == 2
