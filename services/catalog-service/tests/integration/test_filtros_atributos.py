"""Filtros de tipo, unidad y atributos (JSONB con índice GIN) y ficha con atributos, en PostGIS."""

from datetime import UTC, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.criterios_busqueda import CriteriosBusqueda
from app.application.dto.criterios_mapa_servicios import CriteriosMapaServicios
from app.application.dto.escala_mapa import EscalaMapa
from app.application.dto.filtros_servicio import FiltrosServicio
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_alojamiento import BloqueAlojamiento
from app.domain.value_objects.atributos.bloque_comunes import BloqueComunes
from app.domain.value_objects.atributos.bloque_experiencia import BloqueExperiencia
from app.domain.value_objects.atributos.bloque_gastronomia import BloqueGastronomia
from app.domain.value_objects.atributos.bloque_pagos import BloquePagos
from app.domain.value_objects.atributos.credito_prestador import CreditoPrestador
from app.domain.value_objects.atributos.habitacion_ofrecida import HabitacionOfrecida
from app.domain.value_objects.atributos.valores import (
    MedioPago,
    NivelFisico,
    OpcionDietaria,
    RecomendacionDinero,
    SenalInternet,
    TipoCocina,
    TipoHabitacion,
)
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Bbox, Coordenada
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.persistence.consultas.sql_consulta_mapa import SqlConsultaMapa
from app.infrastructure.persistence.consultas.sql_consulta_servicios import SqlConsultaServicios
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

pytestmark = pytest.mark.integration

Sesiones = async_sessionmaker[AsyncSession]
AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
ORIGEN = "https://s3.turismo.local/catalogo-imagenes/"
EN_MINCA = Coordenada(lat=11.1426, lon=-74.1178)

PAGOS_SIN_SENAL = BloquePagos(
    senal_internet=SenalInternet.SIN_SENAL,
    medios_pago=(MedioPago.EFECTIVO,),
    recomendacion_dinero=RecomendacionDinero.EFECTIVO,
    credito=CreditoPrestador(ofrece=True, plazo_dias=3),
)
PAGOS_DIGITAL = BloquePagos(
    senal_internet=SenalInternet.CON_SENAL,
    medios_pago=(MedioPago.EFECTIVO, MedioPago.TARJETA),
    recomendacion_dinero=RecomendacionDinero.CUALQUIERA,
)


def servicio(
    perfil: PrestadorPerfil,
    nombre: str,
    tipo: TipoServicio,
    unidad: UnidadTarifa,
    atributos: AtributosServicio,
) -> AtractivoServicio:
    datos = DatosServicio(
        nombre=TextoTraducido(es=nombre),
        descripcion=TextoTraducido(es="Descripción"),
        tipo=tipo,
        ubicacion=EN_MINCA,
        tarifa_base=Tarifa(Decimal("50000")),
        unidad_tarifa=unidad,
        capacidad_aforo_diario=20,
        atributos=atributos,
    )
    return AtractivoServicio.registrar(perfil, datos, ORIGEN, AHORA)


@pytest.fixture
async def servicios(sesiones: Sesiones) -> dict[str, AtractivoServicio]:
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Minca Viva")
    hostal = servicio(
        perfil,
        "Hostal en la montaña",
        TipoServicio.HOSTAL,
        UnidadTarifa.POR_NOCHE,
        AtributosServicio(
            comunes=BloqueComunes(idiomas_atencion=("es", "en"), mascotas=True),
            alojamiento=BloqueAlojamiento(
                check_in=time(14),
                check_out=time(11),
                habitaciones=(HabitacionOfrecida(TipoHabitacion.DORMITORIO, 6),),
            ),
            pagos=PAGOS_DIGITAL,
        ),
    )
    caminata = servicio(
        perfil,
        "Caminata a Pozo Azul",
        TipoServicio.SENDERISMO,
        UnidadTarifa.POR_PERSONA,
        AtributosServicio(
            comunes=BloqueComunes(accesible=False, apto_ninos=True),
            experiencia=BloqueExperiencia(duracion_minutos=180, nivel_fisico=NivelFisico.MEDIO),
            pagos=PAGOS_SIN_SENAL,
        ),
    )
    restaurante = servicio(
        perfil,
        "Restaurante vegano",
        TipoServicio.RESTAURANTE,
        UnidadTarifa.POR_PERSONA,
        AtributosServicio(
            comunes=BloqueComunes(idiomas_atencion=("es", "fr"), accesible=True),
            gastronomia=BloqueGastronomia(
                tipos_cocina=(TipoCocina.VEGETARIANA,),
                opciones_dietarias=(OpcionDietaria.VEGANA, OpcionDietaria.SIN_GLUTEN),
            ),
        ),
    )
    async with SqlUnidadDeTrabajo(sesiones) as uow:
        await uow.prestadores.guardar(perfil)
        for s in (hostal, caminata, restaurante):
            await uow.servicios.guardar(s)
        await uow.confirmar()
    return {"hostal": hostal, "caminata": caminata, "restaurante": restaurante}


async def nombres(sesiones: Sesiones, **filtros: object) -> set[str]:
    pagina = await SqlConsultaServicios(sesiones).buscar(
        CriteriosBusqueda(idioma=Idioma.ES, filtros=FiltrosServicio(**filtros))  # type: ignore[arg-type]
    )
    return {s.nombre.es for s in pagina.items}


@pytest.mark.parametrize(
    ("filtros", "esperados"),
    [
        ({}, {"Hostal en la montaña", "Caminata a Pozo Azul", "Restaurante vegano"}),
        ({"tipos": (TipoServicio.HOSTAL, TipoServicio.HOTEL)}, {"Hostal en la montaña"}),
        ({"unidad_tarifa": UnidadTarifa.POR_NOCHE}, {"Hostal en la montaña"}),
        ({"idioma_atencion": "en"}, {"Hostal en la montaña"}),
        ({"idioma_atencion": "fr"}, {"Restaurante vegano"}),
        ({"accesible": True}, {"Restaurante vegano"}),
        ({"accesible": False}, {"Caminata a Pozo Azul"}),  # no trae los que no lo informaron
        ({"mascotas": True}, {"Hostal en la montaña"}),
        ({"apto_ninos": True}, {"Caminata a Pozo Azul"}),
        ({"opcion_dietaria": OpcionDietaria.SIN_GLUTEN}, {"Restaurante vegano"}),
        ({"nivel_fisico": NivelFisico.MEDIO}, {"Caminata a Pozo Azul"}),
        ({"acepta_pago_digital": True}, {"Hostal en la montaña"}),
        ({"acepta_pago_digital": False}, {"Caminata a Pozo Azul"}),
        ({"ofrece_credito": True}, {"Caminata a Pozo Azul"}),
        ({"idioma_atencion": "en", "ofrece_credito": True}, set()),  # se combinan con Y
    ],
)
async def test_filtros(
    sesiones: Sesiones, servicios: dict, filtros: dict, esperados: set[str]
) -> None:
    assert await nombres(sesiones, **filtros) == esperados


async def test_resumen_y_ficha_traen_tipo_unidad_y_atributos(
    sesiones: Sesiones, servicios: dict[str, AtractivoServicio]
) -> None:
    consulta = SqlConsultaServicios(sesiones)
    [hostal] = (
        await consulta.buscar(
            CriteriosBusqueda(
                idioma=Idioma.ES, filtros=FiltrosServicio(tipos=(TipoServicio.HOSTAL,))
            )
        )
    ).items
    assert (hostal.tipo, hostal.unidad_tarifa) == (TipoServicio.HOSTAL, UnidadTarifa.POR_NOCHE)

    caminata = servicios["caminata"]
    detalle = await consulta.detalle(caminata.id, AHORA)
    assert detalle is not None
    assert detalle.atributos == caminata.datos.atributos
    assert detalle.atributos.pagos == PAGOS_SIN_SENAL


# Vista alrededor de Minca: zoom 15 trae los servicios uno a uno; zoom 10 los agrupa.
VISTA_MINCA = Bbox(min_lon=-74.13, min_lat=11.13, max_lon=-74.10, max_lat=11.16)


@pytest.mark.parametrize("zoom", [15, 10], ids=["individuales", "agrupados"])
async def test_el_mapa_usa_los_mismos_filtros(
    sesiones: Sesiones, servicios: dict[str, AtractivoServicio], zoom: int
) -> None:
    consulta = SqlConsultaMapa(sesiones)

    async def contar(filtros: FiltrosServicio) -> int:
        mapa = await consulta.servicios(
            CriteriosMapaServicios(vista=VISTA_MINCA, escala=EscalaMapa(zoom), filtros=filtros)
        )
        return len(mapa.servicios) + sum(g.conteo for g in mapa.grupos)

    assert await contar(FiltrosServicio()) == 3
    assert await contar(FiltrosServicio(ofrece_credito=True)) == 1
    assert await contar(FiltrosServicio(tipos=(TipoServicio.RESTAURANTE,), accesible=True)) == 1
    assert await contar(FiltrosServicio(mascotas=True, nivel_fisico=NivelFisico.ALTO)) == 0
