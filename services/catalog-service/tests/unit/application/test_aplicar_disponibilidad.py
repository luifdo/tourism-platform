"""disponibilidad.actualizada → proyección con dobles: versión, validación e idempotencia."""

from datetime import date
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

import pytest

from app.application.dto.disponibilidad_recibida import DisponibilidadRecibida
from app.application.dto.filtros_servicio import FiltrosServicio
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.aplicar_disponibilidad import AplicarDisponibilidad
from app.domain.entities.disponibilidad_dia import DisponibilidadDia
from app.domain.errors import DatoInvalido

SERVICIO, DIA = uuid4(), date(2026, 11, 5)


class Dias:
    def __init__(self) -> None:
        self.datos: dict[tuple[UUID, date], DisponibilidadDia] = {}

    async def obtener(self, servicio_id: UUID, fecha: date) -> DisponibilidadDia | None:
        return self.datos.get((servicio_id, fecha))

    async def guardar(self, dia: DisponibilidadDia) -> None:
        self.datos[(dia.servicio_id, dia.fecha)] = dia


class Procesados:
    def __init__(self) -> None:
        self.ids: set[UUID] = set()

    async def registrar(self, event_id: UUID, consumidor: str) -> bool:
        nuevo = event_id not in self.ids
        self.ids.add(event_id)
        return nuevo


class Unidad:
    def __init__(self) -> None:
        self.disponibilidad, self.eventos_procesados = Dias(), Procesados()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, t: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None
    ) -> None:
        return None

    async def confirmar(self) -> None:
        pass


def recibida(disponibles: int, version: int, totales: int = 10) -> DisponibilidadRecibida:
    return DisponibilidadRecibida(uuid4(), SERVICIO, DIA, totales, disponibles, version)


async def test_versiones_desordenadas_gana_la_mayor() -> None:
    uow = Unidad()
    aplicar = AplicarDisponibilidad(lambda: uow)
    assert await aplicar.execute(recibida(4, 3)) is ResultadoConsumo.APLICADO
    assert await aplicar.execute(recibida(8, 2)) is ResultadoConsumo.IGNORADO  # vieja
    assert await aplicar.execute(recibida(1, 4)) is ResultadoConsumo.APLICADO
    assert uow.disponibilidad.datos[(SERVICIO, DIA)].cupos_disponibles == 1


async def test_duplicado() -> None:
    uow = Unidad()
    aplicar, evento = AplicarDisponibilidad(lambda: uow), recibida(4, 1)
    await aplicar.execute(evento)
    assert await aplicar.execute(evento) is ResultadoConsumo.DUPLICADO


@pytest.mark.parametrize(("totales", "disponibles"), [(5, 6), (-1, 0), (3, -1)])
def test_cupos_incoherentes(totales: int, disponibles: int) -> None:
    with pytest.raises(DatoInvalido):
        DisponibilidadDia(
            servicio_id=SERVICIO,
            fecha=DIA,
            cupos_totales=totales,
            cupos_disponibles=disponibles,
            version=1,
        )


def test_dia_cerrado_no_alcanza() -> None:
    cerrado = DisponibilidadDia(
        servicio_id=SERVICIO, fecha=DIA, cupos_totales=0, cupos_disponibles=0, version=1
    )
    assert not cerrado.alcanza_para(1)


def test_personas_requiere_fecha() -> None:
    with pytest.raises(DatoInvalido, match="requiere"):
        FiltrosServicio(personas=3)
    with pytest.raises(DatoInvalido, match="minimo"):
        FiltrosServicio(fecha=DIA, personas=0)
    assert FiltrosServicio(fecha=DIA, personas=3).personas == 3
