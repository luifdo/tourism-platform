"""reserva.* → proyección con dobles: creación, orden, modificación e idempotencia."""

from datetime import UTC, date, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

import pytest

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.aplicar_evento_reserva import AplicarEventoReserva
from app.domain.entities.reserva_proyeccion import (
    EventoReserva,
    ReservaProyeccion,
    TipoEventoReserva,
)
from app.domain.value_objects.catalogos import EstadoReserva

AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
RESERVA = uuid4()
T = TipoEventoReserva


class Reservas:
    def __init__(self) -> None:
        self.datos: dict[UUID, ReservaProyeccion] = {}

    async def obtener(self, reserva_id: UUID) -> ReservaProyeccion | None:
        return self.datos.get(reserva_id)

    async def guardar(self, reserva: ReservaProyeccion) -> None:
        self.datos[reserva.reserva_id] = reserva


class Procesados:
    def __init__(self) -> None:
        self.ids: set[UUID] = set()

    async def registrar(self, event_id: UUID, consumidor: str) -> bool:
        nuevo = event_id not in self.ids
        self.ids.add(event_id)
        return nuevo


class Unidad:
    def __init__(self) -> None:
        self.reservas, self.eventos_procesados = Reservas(), Procesados()

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


def evento(
    tipo: TipoEventoReserva, minutos: int, fecha: date = date(2026, 11, 5), personas: int = 2
) -> EventoReserva:
    return EventoReserva(
        tipo=tipo,
        reserva_id=RESERVA,
        servicio_id=uuid4(),
        prestador_id=uuid4(),
        turista_id=uuid4(),
        fecha_reserva=fecha,
        numero_personas=personas,
        ocurrido_en=AHORA + timedelta(minutes=minutos),
    )


async def aplicar(uow: Unidad, e: EventoReserva, event_id: UUID | None = None) -> ResultadoConsumo:
    return await AplicarEventoReserva(lambda: uow).execute(event_id or uuid4(), e)


async def test_ciclo_de_vida_completo(uow: Unidad) -> None:
    assert await aplicar(uow, evento(T.SOLICITADA, 0)) is ResultadoConsumo.APLICADO
    assert uow.reservas.datos[RESERVA].activa
    await aplicar(uow, evento(T.CONFIRMADA, 1))
    assert uow.reservas.datos[RESERVA].estado is EstadoReserva.CONFIRMADA
    await aplicar(uow, evento(T.FINALIZADA, 2))
    reserva = uow.reservas.datos[RESERVA]
    assert reserva.estado is EstadoReserva.FINALIZADA and not reserva.activa


async def test_modificada_mueve_fecha_y_personas(uow: Unidad) -> None:
    await aplicar(uow, evento(T.SOLICITADA, 0))
    await aplicar(uow, evento(T.MODIFICADA, 1, fecha=date(2026, 11, 9), personas=4))
    reserva = uow.reservas.datos[RESERVA]
    assert (reserva.fecha_reserva, reserva.numero_personas) == (date(2026, 11, 9), 4)
    assert reserva.estado is EstadoReserva.SOLICITADA


async def test_desordenados_gana_el_mas_nuevo(uow: Unidad) -> None:
    # La confirmación llega antes que la solicitud (por un reintento).
    assert await aplicar(uow, evento(T.CONFIRMADA, 5)) is ResultadoConsumo.APLICADO
    assert await aplicar(uow, evento(T.SOLICITADA, 0)) is ResultadoConsumo.IGNORADO
    assert uow.reservas.datos[RESERVA].estado is EstadoReserva.CONFIRMADA


async def test_cancelada_sale_de_la_demanda(uow: Unidad) -> None:
    await aplicar(uow, evento(T.SOLICITADA, 0))
    await aplicar(uow, evento(T.CANCELADA, 1))
    assert not uow.reservas.datos[RESERVA].activa


async def test_duplicado(uow: Unidad) -> None:
    event_id = uuid4()
    assert await aplicar(uow, evento(T.SOLICITADA, 0), event_id) is ResultadoConsumo.APLICADO
    assert await aplicar(uow, evento(T.SOLICITADA, 0), event_id) is ResultadoConsumo.DUPLICADO
