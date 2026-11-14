"""Atributos por tipo de servicio: bloques, reglas por tipo, pagos en el lugar y JSON."""

from datetime import time
from decimal import Decimal

import pytest

from app.domain.errors import DatoInvalido
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_alojamiento import BloqueAlojamiento
from app.domain.value_objects.atributos.bloque_alquiler import BloqueAlquiler
from app.domain.value_objects.atributos.bloque_comunes import BloqueComunes
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.atributos.bloque_experiencia import BloqueExperiencia
from app.domain.value_objects.atributos.bloque_gastronomia import BloqueGastronomia
from app.domain.value_objects.atributos.bloque_pagos import BloquePagos
from app.domain.value_objects.atributos.bloque_transporte import BloqueTransporte
from app.domain.value_objects.atributos.cajeros_cercanos import CajerosCercanos
from app.domain.value_objects.atributos.credito_prestador import CreditoPrestador
from app.domain.value_objects.atributos.habitacion_ofrecida import HabitacionOfrecida
from app.domain.value_objects.atributos.tarifa_visitante import TarifaVisitante
from app.domain.value_objects.atributos.valores import (
    Amenidad,
    MedioPago,
    NivelFisico,
    OpcionDietaria,
    RecomendacionDinero,
    SenalInternet,
    ServicioEnSitio,
    TipoCocina,
    TipoHabitacion,
    TipoVisitante,
)
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import REGLAS, TipoServicio

EXPERIENCIA = BloqueExperiencia(duracion_minutos=180, nivel_fisico=NivelFisico.MEDIO)
GASTRONOMIA = BloqueGastronomia(tipos_cocina=(TipoCocina.CARIBENA,))
ALOJAMIENTO = BloqueAlojamiento(
    check_in=time(14),
    check_out=time(11),
    habitaciones=(HabitacionOfrecida(TipoHabitacion.DORMITORIO, 8, 2),),
)
SIN_SENAL = BloquePagos(
    senal_internet=SenalInternet.SIN_SENAL,
    medios_pago=(MedioPago.EFECTIVO,),
    recomendacion_dinero=RecomendacionDinero.EFECTIVO,
    credito=CreditoPrestador(
        ofrece=True,
        plazo_dias=3,
        condiciones=TextoTraducido(es="Hasta $100.000; pagas por Nequi al tener señal"),
    ),
    cajeros=CajerosCercanos(
        hay_cerca=False, referencia=TextoTraducido(es="En el parque de Minca"), distancia_km=8
    ),
)


class TestTipos:
    def test_cada_tipo_tiene_regla_y_la_transporte_existe(self) -> None:
        assert set(REGLAS) == set(TipoServicio)
        assert TipoServicio.TRANSPORTE_MARITIMO.categoria is Categoria.TRANSPORTE
        assert {t.categoria for t in TipoServicio} == set(Categoria)

    def test_bloque_principal_obligatorio(self) -> None:
        with pytest.raises(DatoInvalido, match="bloque_obligatorio"):
            AtributosServicio().validar_para(TipoServicio.TOUR_GUIADO)

    def test_bloque_que_no_corresponde(self) -> None:
        atributos = AtributosServicio(experiencia=EXPERIENCIA, alojamiento=ALOJAMIENTO)
        with pytest.raises(DatoInvalido, match="bloque_no_permitido"):
            atributos.validar_para(TipoServicio.TOUR_GUIADO)

    def test_opcionales_comunes_y_pagos_se_admiten(self) -> None:
        AtributosServicio(
            experiencia=EXPERIENCIA, gastronomia=GASTRONOMIA, pagos=SIN_SENAL
        ).validar_para(TipoServicio.EXPERIENCIA_GASTRONOMICA)
        AtributosServicio(alojamiento=ALOJAMIENTO, pagos=SIN_SENAL).validar_para(
            TipoServicio.GLAMPING_CAMPING
        )


class TestBloques:
    def test_idiomas_iso(self) -> None:
        with pytest.raises(DatoInvalido):
            BloqueComunes(idiomas_atencion=("Español",))
        with pytest.raises(DatoInvalido, match="repetido"):
            BloqueComunes(idiomas_atencion=("es", "es"))

    def test_experiencia(self) -> None:
        with pytest.raises(DatoInvalido, match="mayor_que"):
            BloqueExperiencia(
                duracion_minutos=60, nivel_fisico=NivelFisico.BAJO, grupo_minimo=8, grupo_maximo=4
            )
        with pytest.raises(DatoInvalido, match="requiere"):
            BloqueExperiencia(
                duracion_minutos=60, nivel_fisico=NivelFisico.BAJO, idiomas_guia=("en",)
            )
        # Ciudad Perdida: varios días.
        assert BloqueExperiencia(duracion_minutos=4 * 24 * 60, nivel_fisico=NivelFisico.ALTO)

    def test_alojamiento_sin_habitaciones(self) -> None:
        with pytest.raises(DatoInvalido, match="obligatorio"):
            BloqueAlojamiento(check_in=time(14), check_out=time(11), habitaciones=())

    def test_gastronomia_precios(self) -> None:
        with pytest.raises(DatoInvalido, match="mayor_que"):
            BloqueGastronomia(
                tipos_cocina=(TipoCocina.DE_MAR,),
                precio_min_persona=Tarifa(Decimal("50000")),
                precio_max_persona=Tarifa(Decimal("20000")),
            )

    def test_entrada_un_precio_por_visitante(self) -> None:
        precio = Tarifa(Decimal("20000"))
        with pytest.raises(DatoInvalido, match="repetido"):
            BloqueEntrada(
                tarifas=(
                    TarifaVisitante(TipoVisitante.NACIONAL, precio),
                    TarifaVisitante(TipoVisitante.NACIONAL, precio),
                )
            )


class TestPagos:
    def test_recomendar_digital_exige_medio_digital(self) -> None:
        with pytest.raises(DatoInvalido, match="recomendacion_sin_medio"):
            BloquePagos(
                senal_internet=SenalInternet.CON_SENAL,
                medios_pago=(MedioPago.EFECTIVO,),
                recomendacion_dinero=RecomendacionDinero.DIGITAL,
            )

    def test_recomendar_efectivo_exige_aceptarlo(self) -> None:
        with pytest.raises(DatoInvalido, match="recomendacion_sin_medio"):
            BloquePagos(
                senal_internet=SenalInternet.INTERMITENTE,
                medios_pago=(MedioPago.TRANSFERENCIA,),
                recomendacion_dinero=RecomendacionDinero.EFECTIVO,
            )

    def test_condiciones_de_credito_sin_ofrecerlo(self) -> None:
        with pytest.raises(DatoInvalido, match="requiere"):
            CreditoPrestador(ofrece=False, plazo_dias=3)

    def test_distancia_al_cajero(self) -> None:
        with pytest.raises(DatoInvalido, match="rango"):
            CajerosCercanos(hay_cerca=False, distancia_km=500)

    def test_acepta_pago_digital_se_guarda_para_filtrar(self) -> None:
        assert SIN_SENAL.a_json()["acepta_pago_digital"] is False
        digital = BloquePagos(
            senal_internet=SenalInternet.CON_SENAL,
            medios_pago=(MedioPago.EFECTIVO, MedioPago.TRANSFERENCIA),
            recomendacion_dinero=RecomendacionDinero.CUALQUIERA,
        )
        assert digital.a_json()["acepta_pago_digital"] is True


def test_ida_y_vuelta_por_json_con_todos_los_bloques() -> None:
    atributos = AtributosServicio(
        comunes=BloqueComunes(
            horario=TextoTraducido(es="Todos los días 6:00–17:00", en="Daily 6:00–17:00"),
            idiomas_atencion=("es", "en"),
            accesible=False,
            mascotas=True,
            certificacion_sostenible=" NTS-TS 002 ",
        ),
        alojamiento=BloqueAlojamiento(
            check_in=time(15),
            check_out=time(11, 30),
            habitaciones=(HabitacionOfrecida(TipoHabitacion.PRIVADA, 2, 5),),
            amenidades=(Amenidad.WIFI, Amenidad.VENTILADOR),
            desayuno_incluido=True,
        ),
        experiencia=BloqueExperiencia(
            duracion_minutos=240,
            nivel_fisico=NivelFisico.ALTO,
            grupo_minimo=2,
            grupo_maximo=12,
            incluye_guia=True,
            idiomas_guia=("es", "en"),
        ),
        gastronomia=BloqueGastronomia(
            tipos_cocina=(TipoCocina.DE_MAR,),
            opciones_dietarias=(OpcionDietaria.VEGANA,),
            precio_min_persona=Tarifa(Decimal("25000")),
            precio_max_persona=Tarifa(Decimal("60000.50")),
        ),
        entrada=BloqueEntrada(
            tarifas=(TarifaVisitante(TipoVisitante.EXTRANJERO, Tarifa(Decimal("73500"))),),
            servicios_en_sitio=(ServicioEnSitio.BANOS,),
        ),
        alquiler=BloqueAlquiler(
            equipos=TextoTraducido(es="Carpa y sillas"), deposito=Tarifa(Decimal("50000"))
        ),
        transporte=BloqueTransporte(
            origen=TextoTraducido(es="Taganga"),
            destino=TextoTraducido(es="Playa Cristal"),
            duracion_minutos=40,
            capacidad_vehiculo=12,
            horarios_salida=(time(10), time(8)),
            incluye_chaleco_salvavidas=True,
        ),
        pagos=SIN_SENAL,
    )
    json = atributos.a_json()
    assert json["alojamiento"]["check_out"] == "11:30"
    assert json["gastronomia"]["precio_max_persona"] == "60000.50"
    assert json["transporte"]["horarios_salida"] == ["08:00", "10:00"]  # ordenados
    assert "apto_ninos" not in json["comunes"]  # solo lo informado
    assert AtributosServicio.desde_json(json) == atributos


def test_json_vacio_son_solo_los_comunes_por_defecto() -> None:
    assert AtributosServicio.desde_json({}) == AtributosServicio()
    assert AtributosServicio().a_json() == {"comunes": {"idiomas_atencion": ["es"]}}
