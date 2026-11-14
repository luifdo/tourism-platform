"""Capacidad de carga (UC24) con una consulta falsa: índice, banderas, orden, roles y zonas."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.dto.carga_de_servicio import CargaDeServicio
from app.application.dto.cargas_capacidad import CargasCapacidad
from app.application.dto.cargas_de_zona import CargasDeZona
from app.application.dto.zona_resumen import ZonaResumen
from app.application.use_cases.consultar_capacidad import ConsultarCapacidad
from app.domain.errors import NoEncontrado, RolNoPermitido
from app.domain.services.calculadora_saturacion import CargaServicio
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.saturacion import NivelSaturacion
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.infrastructure.tareas.tarea_periodica import TareaPeriodica

HOY = date(2026, 10, 23)
LEIDO = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
ENTIDAD = Identidad(uuid4(), Rol.ENTIDAD)


class RelojFijo:
    def ahora(self) -> datetime:
        return LEIDO

    def hoy(self) -> date:
        return HOY


def servicio(nombre: str, personas: int, capacidad: int, activo: bool = True) -> CargaDeServicio:
    return CargaDeServicio(
        uuid4(), TextoTraducido(es=nombre), CargaServicio(personas, capacidad, activo)
    )


def zona(codigo: str, *servicios: CargaDeServicio) -> CargasDeZona:
    return CargasDeZona(uuid4(), ZonaResumen(codigo, TextoTraducido(es=codigo)), servicios)


class ConsultaFalsa:
    def __init__(self, *zonas: CargasDeZona) -> None:
        self.zonas = zonas
        self.pedido: tuple[date, str | None] | None = None

    async def cargas(self, fecha: date, zona: str | None = None) -> CargasCapacidad:
        self.pedido = (fecha, zona)
        elegidas = tuple(z for z in self.zonas if zona is None or z.zona.codigo == zona)
        return CargasCapacidad(fecha=fecha, zonas=elegidas, leido_en=LEIDO)


async def test_indice_banderas_y_orden() -> None:
    consulta = ConsultaFalsa(
        zona("minca", servicio("Pozo Azul", 18, 20), servicio("Café", 2, 30)),  # 20/50 = 0,4
        zona("tayrona", servicio("Cabo", 90, 100)),  # 0,9: ALTO
        zona("vacia"),  # sin servicios: no sale
    )
    resultado = await ConsultarCapacidad(consulta, RelojFijo()).execute(ENTIDAD)
    assert consulta.pedido == (HOY, None)  # hoy por defecto
    assert [c.zona.codigo for c in resultado] == ["tayrona", "minca"]  # más presionada primero
    tayrona, minca = resultado
    assert (tayrona.saturacion.indice, tayrona.saturacion.nivel) == (0.9, NivelSaturacion.ALTO)
    assert [b.nombre.es for b in tayrona.servicios_con_bandera] == ["Cabo"]
    # La zona está en BAJO, pero Pozo Azul (0,9) ya tiene bandera.
    assert minca.saturacion.nivel is NivelSaturacion.BAJO
    assert [b.nombre.es for b in minca.servicios_con_bandera] == ["Pozo Azul"]
    assert minca.calculado_en == LEIDO


async def test_un_servicio_apagado_sin_reservas_no_infla_la_capacidad() -> None:
    consulta = ConsultaFalsa(
        zona("minca", servicio("Abierto", 10, 20), servicio("Cerrado", 0, 80, activo=False))
    )
    [minca] = await ConsultarCapacidad(consulta, RelojFijo()).execute(ENTIDAD)
    assert minca.saturacion.capacidad == 20


async def test_zona_inexistente_es_404_y_sin_servicios_es_lista_vacia() -> None:
    consulta = ConsultaFalsa(zona("vacia"))
    caso = ConsultarCapacidad(consulta, RelojFijo())
    with pytest.raises(NoEncontrado):
        await caso.execute(ENTIDAD, zona="no-existe")
    assert await caso.execute(ENTIDAD, zona="vacia") == []


async def test_roles() -> None:
    caso = ConsultarCapacidad(ConsultaFalsa(), RelojFijo())
    assert await caso.execute(Identidad(uuid4(), Rol.TURISTA)) == []
    with pytest.raises(RolNoPermitido):
        await caso.execute(Identidad(uuid4(), Rol.PRESTADOR))


async def test_la_tarea_periodica_sigue_aunque_falle() -> None:
    llamadas: list[int] = []
    detener = asyncio.Event()

    async def ejecutar() -> None:
        llamadas.append(1)
        if len(llamadas) == 1:
            raise RuntimeError("PostgreSQL no responde")
        if len(llamadas) == 3:
            detener.set()

    await asyncio.wait_for(
        TareaPeriodica("prueba", timedelta(milliseconds=10), ejecutar).correr(detener), 2
    )
    assert len(llamadas) == 3
