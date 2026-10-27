"""Reporte CSV (UC38) con dobles: formato para Excel en español, fórmulas, auditoría y roles."""

import csv
import io
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Self
from uuid import uuid4

import pytest

from app.api.reportes.csv_reporte_demanda import ENCABEZADOS, generar_csv, texto_seguro
from app.application.dto.fila_reporte_demanda import FilaReporteDemanda
from app.application.dto.rango_fechas import RangoFechas
from app.application.dto.zona_vista import ZonaVista
from app.application.use_cases.exportar_reporte_demanda import ExportarReporteDemanda
from app.domain.errors import NoEncontrado, RolNoPermitido
from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.domain.events.evento_dominio import EventoDominio
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio

AHORA = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
RANGO = RangoFechas(date(2026, 11, 1), date(2026, 11, 30))
ENTIDAD = Identidad(uuid4(), Rol.ENTIDAD)


def fila(servicio: str = "Pozo Azul", **cambios: object) -> FilaReporteDemanda:
    base = {
        "fecha": date(2026, 11, 3),
        "zona": "Minca",
        "servicio": servicio,
        "categoria": Categoria.NATURALEZA,
        "tipo": TipoServicio.RESERVA_PARQUE,
        "personas_solicitadas": 2,
        "personas_confirmadas": 5,
        "personas_finalizadas": 5,
        "personas_canceladas": 3,
        "capacidad_recomendada": 10,
        "intenciones_visita": 4,
    }
    return FilaReporteDemanda(**(base | cambios))  # type: ignore[arg-type]


async def iterar(*filas: FilaReporteDemanda) -> AsyncIterator[FilaReporteDemanda]:
    for f in filas:
        yield f


async def leer(*filas: FilaReporteDemanda) -> tuple[bytes, list[list[str]]]:
    contenido = b"".join([parte async for parte in generar_csv(iterar(*filas))])
    texto = contenido.decode("utf-8").removeprefix("﻿")
    return contenido, list(csv.reader(io.StringIO(texto), delimiter=";"))


async def test_formato_para_excel_en_espanol() -> None:
    contenido, filas = await leer(fila())
    assert contenido.startswith("﻿".encode())  # BOM: Excel muestra bien las tildes
    encabezado, datos = filas
    assert tuple(encabezado) == ENCABEZADOS
    assert encabezado[5:10] == [
        "Personas solicitadas",
        "Personas confirmadas",
        "Personas finalizadas",
        "Personas canceladas",
        "Total de personas",
    ]
    assert datos == [
        "2026-11-03", "Minca", "Pozo Azul", "Naturaleza", "Reserva o parque",
        "2", "5", "5", "3", "12", "10", "1,20", "4",
    ]  # fmt: skip


async def test_sin_zona_la_celda_queda_vacia() -> None:
    _, filas = await leer(fila(zona=None))
    assert filas[1][1] == ""


@pytest.mark.parametrize("peligroso", ['=HYPERLINK("http://x")', "+57 300", "-1", "@SUM(A1)"])
async def test_un_nombre_que_parece_formula_queda_como_texto(peligroso: str) -> None:
    _, filas = await leer(fila(servicio=peligroso))
    assert filas[1][2] == f"'{peligroso}"
    assert texto_seguro("Pozo Azul") == "Pozo Azul"


class ZonasFalsas:
    async def activas(self) -> list[ZonaVista]:
        return [ZonaVista(uuid4(), "minca", TextoTraducido(es="Minca"), Coordenada(11.14, -74.11))]


class AnaliticaFalsa:
    def filas_reporte_demanda(
        self, rango: RangoFechas, zona: str | None
    ) -> AsyncIterator[FilaReporteDemanda]:
        return iterar(fila())


class Outbox:
    def __init__(self) -> None:
        self.eventos: list[EventoDominio] = []

    async def agregar(self, evento: EventoDominio) -> None:
        self.eventos.append(evento)


class Unidad:
    def __init__(self) -> None:
        self.outbox = Outbox()
        self.confirmada = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, t: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None
    ) -> None:
        return None

    async def confirmar(self) -> None:
        self.confirmada = True


class RelojFijo:
    def ahora(self) -> datetime:
        return AHORA

    def hoy(self) -> date:
        return AHORA.date()


def caso(uow: Unidad) -> ExportarReporteDemanda:
    return ExportarReporteDemanda(AnaliticaFalsa(), ZonasFalsas(), lambda: uow, RelojFijo())


async def test_la_exportacion_se_audita_antes_de_entregar() -> None:
    uow = Unidad()
    filas = await caso(uow).execute(ENTIDAD, RANGO, "minca")
    [evento] = uow.outbox.eventos
    assert isinstance(evento, AuditoriaRegistrada) and uow.confirmada
    assert evento.payload()["accion"] == "EXPORT"
    assert evento.detalles == {
        "reporte": "demanda",
        "formato": "csv",
        "desde": "2026-11-01",
        "hasta": "2026-11-30",
        "zona": "minca",
    }
    assert [f.servicio async for f in filas] == ["Pozo Azul"]


async def test_roles_y_zona_inexistente_no_auditan() -> None:
    uow = Unidad()
    with pytest.raises(RolNoPermitido):
        await caso(uow).execute(Identidad(uuid4(), Rol.PRESTADOR), RANGO)
    with pytest.raises(NoEncontrado):
        await caso(uow).execute(ENTIDAD, RANGO, "no-existe")
    assert uow.outbox.eventos == []
