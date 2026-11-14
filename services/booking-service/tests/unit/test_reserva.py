from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from domain.errores import FueraDePlazo, NoDisponible, PlazoVencido, TransicionInvalida, Validacion
from domain.reglas import ZONA
from domain.reserva import MOTIVO_PLAZO_VENCIDO, Actor, EstadoReserva, Reserva
from domain.servicio import ServicioRef

AHORA = datetime(2026, 11, 1, 10, 0, tzinfo=ZONA)
FECHA = date(2026, 11, 10)


def servicio(activo: bool = True) -> ServicioRef:
    return ServicioRef(uuid4(), uuid4(), uuid4(), 20, Decimal("50000"), activo, 1)


def solicitada(personas: int = 2, fecha: date = FECHA) -> Reserva:
    r = Reserva.solicitar(servicio(), uuid4(), fecha, personas, AHORA)
    r.extraer_eventos()
    return r


def confirmada() -> Reserva:
    r = solicitada()
    r.confirmar(AHORA)
    r.extraer_eventos()
    return r


def tipos(r: Reserva) -> list[str]:
    return [e.tipo for e in r.extraer_eventos()]


class TestSolicitar:
    def test_crea_en_solicitada_con_plazo_y_evento(self):
        s = servicio()
        r = Reserva.solicitar(s, uuid4(), FECHA, 2, AHORA)
        assert r.estado is EstadoReserva.SOLICITADA
        assert (r.prestador_id, r.prestador_usuario_id) == (s.prestador_id, s.prestador_usuario_id)
        assert r.expira_en == AHORA + timedelta(hours=48)
        [evento] = r.extraer_eventos()
        assert evento.tipo == "reserva.solicitada"
        assert evento.payload == {
            "reserva_id": str(r.id),
            "servicio_id": str(r.servicio_id),
            "turista_id": str(r.turista_id),
            "prestador_id": str(r.prestador_id),
            "fecha_reserva": "2026-11-10",
            "numero_personas": 2,
        }

    def test_el_evento_lleva_el_perfil_no_el_usuario_del_prestador(self):
        r = Reserva.solicitar(servicio(), uuid4(), FECHA, 2, AHORA)
        [evento] = r.extraer_eventos()
        assert evento.payload["prestador_id"] == str(r.prestador_id)
        assert str(r.prestador_usuario_id) not in evento.payload.values()

    def test_servicio_inactivo_no_acepta_solicitudes(self):
        with pytest.raises(NoDisponible):
            Reserva.solicitar(servicio(activo=False), uuid4(), FECHA, 2, AHORA)

    def test_exige_al_menos_una_persona(self):
        with pytest.raises(Validacion):
            solicitada(personas=0)

    def test_no_acepta_el_mismo_dia(self):
        with pytest.raises(Validacion):
            solicitada(fecha=AHORA.date())


class TestModificar:
    def test_cambia_fecha_y_personas_y_reinicia_el_plazo(self):
        r = solicitada()
        despues = AHORA + timedelta(hours=30)
        r.modificar(despues, fecha_reserva=date(2026, 11, 20), numero_personas=4)
        assert (r.fecha_reserva, r.numero_personas) == (date(2026, 11, 20), 4)
        assert r.expira_en == despues + timedelta(hours=48)
        [evento] = r.extraer_eventos()
        assert evento.tipo == "reserva.modificada"
        assert evento.payload["fecha_anterior"] == "2026-11-10"
        assert evento.payload["numero_personas_anterior"] == 2
        assert evento.payload["expira_en"] == r.expira_en.isoformat()

    def test_exige_algun_cambio(self):
        with pytest.raises(Validacion):
            solicitada().modificar(AHORA)

    def test_cero_personas_no_conserva_el_valor_anterior(self):
        with pytest.raises(Validacion):
            solicitada().modificar(AHORA, numero_personas=0)

    def test_solo_en_solicitada(self):
        with pytest.raises(TransicionInvalida):
            confirmada().modificar(AHORA, numero_personas=3)


class TestConfirmarYRechazar:
    def test_confirmar(self):
        r = solicitada()
        r.confirmar(AHORA)
        assert r.estado is EstadoReserva.CONFIRMADA and r.expira_en is None
        assert tipos(r) == ["reserva.confirmada"]

    def test_confirmar_con_plazo_vencido(self):
        r = solicitada()
        with pytest.raises(PlazoVencido):
            r.confirmar(r.expira_en)

    def test_confirmar_dos_veces(self):
        with pytest.raises(TransicionInvalida):
            confirmada().confirmar(AHORA)

    def test_rechazar_con_motivo(self):
        r = solicitada()
        r.rechazar("  Sin guía disponible ", AHORA)
        assert (r.estado, r.motivo) == (EstadoReserva.RECHAZADA, "Sin guía disponible")
        [evento] = r.extraer_eventos()
        assert evento.payload["motivo"] == "Sin guía disponible"

    @pytest.mark.parametrize("motivo", ["", "  ", "no"])
    def test_rechazar_exige_motivo(self, motivo):
        with pytest.raises(Validacion):
            solicitada().rechazar(motivo, AHORA)


class TestExpirar:
    def test_expira_al_vencer_el_plazo(self):
        r = solicitada()
        r.expirar(r.expira_en)
        assert (r.estado, r.motivo) == (EstadoReserva.RECHAZADA, MOTIVO_PLAZO_VENCIDO)
        assert tipos(r) == ["reserva.rechazada"]

    def test_no_expira_antes(self):
        r = solicitada()
        with pytest.raises(TransicionInvalida):
            r.expirar(r.expira_en - timedelta(seconds=1))


class TestCancelar:
    def test_turista_cancela_solicitada(self):
        r = solicitada()
        r.cancelar(Actor.TURISTA, AHORA)
        assert (r.estado, r.cancelada_por) == (EstadoReserva.CANCELADA, Actor.TURISTA)
        [evento] = r.extraer_eventos()
        assert evento.payload["cancelada_por"] == "Turista"
        assert "motivo" not in evento.payload

    def test_turista_cancela_confirmada_hasta_el_dia_anterior(self):
        r = confirmada()
        r.cancelar(Actor.TURISTA, datetime(2026, 11, 9, 23, 59, tzinfo=ZONA))
        assert r.estado is EstadoReserva.CANCELADA

    def test_turista_no_cancela_confirmada_el_mismo_dia(self):
        with pytest.raises(FueraDePlazo):
            confirmada().cancelar(Actor.TURISTA, datetime(2026, 11, 10, 6, 0, tzinfo=ZONA))

    def test_prestador_cancela_confirmada_con_motivo(self):
        r = confirmada()
        r.cancelar(Actor.PRESTADOR, datetime(2026, 11, 10, 6, 0, tzinfo=ZONA), "Alerta oficial de oleaje")
        [evento] = r.extraer_eventos()
        assert evento.payload["cancelada_por"] == "Prestador"
        assert evento.payload["motivo"] == "Alerta oficial de oleaje"

    def test_prestador_exige_motivo(self):
        with pytest.raises(Validacion):
            confirmada().cancelar(Actor.PRESTADOR, AHORA)

    def test_prestador_no_cancela_solicitada_debe_rechazarla(self):
        with pytest.raises(TransicionInvalida):
            solicitada().cancelar(Actor.PRESTADOR, AHORA, "Motivo")

    def test_no_se_cancela_una_reserva_cerrada(self):
        r = solicitada()
        r.cancelar(Actor.TURISTA, AHORA)
        with pytest.raises(TransicionInvalida):
            r.cancelar(Actor.TURISTA, AHORA)


class TestFinalizar:
    def test_finaliza_al_dia_siguiente(self):
        r = confirmada()
        r.finalizar(datetime(2026, 11, 11, 0, 0, tzinfo=ZONA))
        assert r.estado is EstadoReserva.FINALIZADA
        assert tipos(r) == ["reserva.finalizada"]

    def test_no_finaliza_el_mismo_dia(self):
        with pytest.raises(TransicionInvalida):
            confirmada().finalizar(datetime(2026, 11, 10, 23, 0, tzinfo=ZONA))

    def test_solo_desde_confirmada(self):
        with pytest.raises(TransicionInvalida):
            solicitada().finalizar(datetime(2026, 11, 11, 0, 0, tzinfo=ZONA))


def test_cada_transicion_sube_la_version():
    r = solicitada()
    r.confirmar(AHORA)
    r.cancelar(Actor.TURISTA, AHORA)
    assert r.version == 3
