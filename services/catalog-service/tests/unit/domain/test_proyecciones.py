from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.calificacion_resena import CalificacionResena
from app.domain.entities.reserva_proyeccion import (
    EventoReserva,
    ReservaProyeccion,
    TipoEventoReserva,
)
from app.domain.errors import DatoInvalido
from app.domain.value_objects.catalogos import EstadoReserva

T0 = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
RESERVA, SERVICIO, PRESTADOR, TURISTA = uuid4(), uuid4(), uuid4(), uuid4()


def evento(
    tipo: TipoEventoReserva, minutos: int, fecha: date = date(2026, 11, 5), personas: int = 2
) -> EventoReserva:
    return EventoReserva(
        tipo=tipo,
        reserva_id=RESERVA,
        servicio_id=SERVICIO,
        prestador_id=PRESTADOR,
        turista_id=TURISTA,
        fecha_reserva=fecha,
        numero_personas=personas,
        ocurrido_en=T0 + timedelta(minutes=minutos),
    )


class TestReservaProyeccion:
    def test_ciclo_normal(self) -> None:
        r = ReservaProyeccion.desde_evento(evento(TipoEventoReserva.SOLICITADA, 0))
        assert r.activa
        assert r.aplicar(evento(TipoEventoReserva.CONFIRMADA, 5))
        assert r.estado is EstadoReserva.CONFIRMADA and r.activa
        assert r.aplicar(evento(TipoEventoReserva.FINALIZADA, 60))
        assert r.estado is EstadoReserva.FINALIZADA and not r.activa

    def test_duplicado_no_cambia_nada(self) -> None:
        r = ReservaProyeccion.desde_evento(evento(TipoEventoReserva.SOLICITADA, 0))
        assert r.aplicar(evento(TipoEventoReserva.SOLICITADA, 0)) is False

    def test_evento_viejo_que_llega_tarde_se_ignora(self) -> None:
        # La confirmación llegó primero (la solicitud se reintentó desde la DLQ).
        r = ReservaProyeccion.desde_evento(evento(TipoEventoReserva.CONFIRMADA, 5))
        assert r.aplicar(evento(TipoEventoReserva.SOLICITADA, 0)) is False
        assert r.estado is EstadoReserva.CONFIRMADA

    def test_cancelada_no_revive_con_un_evento_anterior(self) -> None:
        r = ReservaProyeccion.desde_evento(evento(TipoEventoReserva.SOLICITADA, 0))
        r.aplicar(evento(TipoEventoReserva.CANCELADA, 10))
        assert r.aplicar(evento(TipoEventoReserva.CONFIRMADA, 5)) is False
        assert not r.activa

    def test_modificada_mueve_fecha_y_personas(self) -> None:
        r = ReservaProyeccion.desde_evento(evento(TipoEventoReserva.SOLICITADA, 0))
        r.aplicar(evento(TipoEventoReserva.MODIFICADA, 3, fecha=date(2026, 11, 6), personas=4))
        assert (r.fecha_reserva, r.numero_personas, r.estado) == (
            date(2026, 11, 6),
            4,
            EstadoReserva.SOLICITADA,
        )

    @pytest.mark.parametrize(
        ("tipo", "estado"),
        [
            (TipoEventoReserva.SOLICITADA, EstadoReserva.SOLICITADA),
            (TipoEventoReserva.MODIFICADA, EstadoReserva.SOLICITADA),
            (TipoEventoReserva.CONFIRMADA, EstadoReserva.CONFIRMADA),
            (TipoEventoReserva.RECHAZADA, EstadoReserva.RECHAZADA),
            (TipoEventoReserva.CANCELADA, EstadoReserva.CANCELADA),
            (TipoEventoReserva.FINALIZADA, EstadoReserva.FINALIZADA),
        ],
    )
    def test_estado_resultante(self, tipo: TipoEventoReserva, estado: EstadoReserva) -> None:
        assert tipo.estado_resultante is estado

    def test_tipos_coinciden_con_las_claves_de_enrutamiento(self) -> None:
        assert TipoEventoReserva("reserva.modificada") is TipoEventoReserva.MODIFICADA


class TestCalificacionResena:
    @pytest.mark.parametrize("puntuacion", [0, 6])
    def test_rango(self, puntuacion: int) -> None:
        with pytest.raises(DatoInvalido):
            CalificacionResena(resena_id=uuid4(), servicio_id=uuid4(), puntuacion=puntuacion)
