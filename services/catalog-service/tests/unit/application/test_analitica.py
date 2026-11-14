"""Analítica (UC22, UC23, UC25) con dobles: periodos, ceros, ocupación sin tope y roles."""

from datetime import date
from uuid import UUID, uuid4

import pytest

from app.application.dto.agrupacion_demanda import AgrupacionDemanda
from app.application.dto.fila_metricas_servicio import FilaMetricasServicio
from app.application.dto.punto_demanda import PuntoDemanda
from app.application.dto.rango_fechas import RangoFechas
from app.application.dto.reservas_por_estado import ReservasPorEstado
from app.application.dto.zona_demandada import ZonaDemandada
from app.application.dto.zona_vista import ZonaVista
from app.application.use_cases.consultar_demanda import ConsultarDemanda, periodos
from app.application.use_cases.obtener_metricas_prestador import ObtenerMetricasPrestador
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.errors import NoEncontrado, PerfilInactivo, RolNoPermitido
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.texto_traducido import TextoTraducido

ENTIDAD = Identidad(uuid4(), Rol.ENTIDAD)
SEMANA = AgrupacionDemanda.SEMANA


class AnaliticaFalsa:
    def __init__(self, puntos: list[PuntoDemanda] | None = None, capacidad: int = 10) -> None:
        self.puntos = puntos or []
        self.capacidad = capacidad

    async def metricas_prestador(
        self, prestador_id: UUID, rango: RangoFechas
    ) -> list[FilaMetricasServicio]:
        return [
            FilaMetricasServicio(
                servicio_id=uuid4(),
                nombre=TextoTraducido(es="Pozo Azul"),
                capacidad_aforo_diario=self.capacidad,
                reservas=ReservasPorEstado(finalizadas=3),
                personas_finalizadas=36,
                calificacion_promedio=4.5,
                total_resenas=2,
                intenciones_visita=7,
            )
        ]

    async def demanda(
        self,
        rango: RangoFechas,
        agrupacion: AgrupacionDemanda,
        zona: str | None,
        categoria: Categoria | None,
    ) -> list[PuntoDemanda]:
        return self.puntos

    async def totales(self, rango: RangoFechas) -> PuntoDemanda:
        return PuntoDemanda(periodo=rango.desde)

    async def zonas_mas_demandadas(self, rango: RangoFechas, limite: int) -> list[ZonaDemandada]:
        return []


class ZonasFalsas:
    async def activas(self) -> list[ZonaVista]:
        return [ZonaVista(uuid4(), "minca", TextoTraducido(es="Minca"), Coordenada(11.14, -74.11))]


class PrestadorFalso:
    def __init__(self, perfil: PrestadorPerfil | None) -> None:
        self.perfil = perfil

    async def perfil_de_usuario(self, usuario_id: UUID) -> PrestadorPerfil | None:
        return self.perfil


def test_las_semanas_empiezan_el_lunes_y_los_meses_cruzan_el_anio() -> None:
    # 2026-10-01 es jueves: la primera semana empieza el lunes 28 de septiembre.
    assert periodos(RangoFechas(date(2026, 10, 1), date(2026, 10, 14)), SEMANA) == [
        date(2026, 9, 28),
        date(2026, 10, 5),
        date(2026, 10, 12),
    ]
    assert periodos(RangoFechas(date(2026, 11, 15), date(2027, 1, 3)), AgrupacionDemanda.MES) == [
        date(2026, 11, 1),
        date(2026, 12, 1),
        date(2027, 1, 1),
    ]
    assert (
        len(periodos(RangoFechas(date(2026, 10, 1), date(2026, 10, 31)), AgrupacionDemanda.DIA))
        == 31
    )


async def test_los_periodos_sin_reservas_salen_en_cero() -> None:
    con_datos = PuntoDemanda(periodo=date(2026, 10, 5), confirmadas=12, zona="minca")
    serie = await ConsultarDemanda(AnaliticaFalsa([con_datos]), ZonasFalsas()).execute(
        ENTIDAD, RangoFechas(date(2026, 10, 1), date(2026, 10, 14)), SEMANA, zona="minca"
    )
    assert [(p.periodo.day, p.confirmadas, p.zona) for p in serie.serie] == [
        (28, 0, "minca"),
        (5, 12, "minca"),
        (12, 0, "minca"),
    ]


async def test_demanda_de_una_zona_inexistente_y_roles() -> None:
    caso = ConsultarDemanda(AnaliticaFalsa(), ZonasFalsas())
    rango = RangoFechas(date(2026, 10, 1), date(2026, 10, 2))
    with pytest.raises(NoEncontrado):
        await caso.execute(ENTIDAD, rango, zona="no-existe")
    with pytest.raises(RolNoPermitido):
        await caso.execute(Identidad(uuid4(), Rol.PRESTADOR), rango)


async def test_la_ocupacion_puede_pasar_de_uno() -> None:
    # 36 personas en 3 días con aforo recomendado de 10 por día: 120 %.
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Minca Viva")
    metricas = await ObtenerMetricasPrestador(PrestadorFalso(perfil), AnaliticaFalsa()).execute(
        Identidad(perfil.usuario_id, Rol.PRESTADOR),
        RangoFechas(date(2026, 10, 1), date(2026, 10, 3)),
    )
    assert metricas.servicios[0].ocupacion == 1.2


async def test_metricas_suspendido_si_y_sin_perfil_no() -> None:
    suspendido = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Minca Viva")
    suspendido.suspender()
    rango = RangoFechas(date(2026, 10, 1), date(2026, 10, 1))
    caso = ObtenerMetricasPrestador(PrestadorFalso(suspendido), AnaliticaFalsa())
    assert len((await caso.execute(Identidad(uuid4(), Rol.PRESTADOR), rango)).servicios) == 1
    with pytest.raises(PerfilInactivo):
        await ObtenerMetricasPrestador(PrestadorFalso(None), AnaliticaFalsa()).execute(
            Identidad(uuid4(), Rol.PRESTADOR), rango
        )
    with pytest.raises(RolNoPermitido):
        await caso.execute(ENTIDAD, rango)
