"""resena.publicada / resena.ocultada con dobles: visibilidad, orden e idempotencia."""

from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

import pytest

from app.application.dto.resena_recibida import ResenaRecibida
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.aplicar_evento_resena import AplicarEventoResena
from app.domain.entities.calificacion_resena import CalificacionResena
from app.domain.errors import DatoInvalido

AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
RESENA, SERVICIO = uuid4(), uuid4()


class Calificaciones:
    def __init__(self) -> None:
        self.datos: dict[UUID, CalificacionResena] = {}

    async def obtener(self, resena_id: UUID) -> CalificacionResena | None:
        return self.datos.get(resena_id)

    async def guardar(self, calificacion: CalificacionResena) -> None:
        self.datos[calificacion.resena_id] = calificacion


class Procesados:
    def __init__(self) -> None:
        self.ids: set[UUID] = set()

    async def registrar(self, event_id: UUID, consumidor: str) -> bool:
        nuevo = event_id not in self.ids
        self.ids.add(event_id)
        return nuevo


class Unidad:
    def __init__(self) -> None:
        self.calificaciones, self.eventos_procesados = Calificaciones(), Procesados()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, t: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None
    ) -> None:
        return None

    async def confirmar(self) -> None:
        pass


@pytest.fixture
def uow() -> Unidad:
    return Unidad()


def resena(visible: bool, minutos: int, puntuacion: int = 2) -> ResenaRecibida:
    return ResenaRecibida(
        uuid4(), AHORA + timedelta(minutes=minutos), RESENA, SERVICIO, puntuacion, visible
    )


async def aplicar(uow: Unidad, r: ResenaRecibida) -> ResultadoConsumo:
    return await AplicarEventoResena(lambda: uow).execute(r)


async def test_publicar_ocultar_y_volver_a_publicar(uow: Unidad) -> None:
    assert await aplicar(uow, resena(True, 0)) is ResultadoConsumo.APLICADO
    assert uow.calificaciones.datos[RESENA].visible
    await aplicar(uow, resena(False, 1))
    assert not uow.calificaciones.datos[RESENA].visible
    await aplicar(uow, resena(True, 2))
    assert uow.calificaciones.datos[RESENA].visible


async def test_una_publicacion_vieja_no_deshace_la_ocultacion(uow: Unidad) -> None:
    # La ocultación llega primero (crea la fila oculta); la publicación original, después.
    assert await aplicar(uow, resena(False, 5)) is ResultadoConsumo.APLICADO
    assert await aplicar(uow, resena(True, 0)) is ResultadoConsumo.IGNORADO
    assert not uow.calificaciones.datos[RESENA].visible


async def test_duplicado(uow: Unidad) -> None:
    r = resena(True, 0)
    await aplicar(uow, r)
    assert await aplicar(uow, r) is ResultadoConsumo.DUPLICADO


def test_puntuacion_fuera_de_rango() -> None:
    with pytest.raises(DatoInvalido):
        CalificacionResena.desde_evento(RESENA, SERVICIO, 6, True, AHORA)
    c = CalificacionResena.desde_evento(RESENA, SERVICIO, 4, True, AHORA)
    with pytest.raises(DatoInvalido):
        c.aplicar(0, True, AHORA + timedelta(minutes=1))
