from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from domain.disponibilidad import DisponibilidadCupo
from domain.errores import CuposComprometidos, CuposInsuficientes, SuperaAforo, Validacion


def dia(totales: int = 10, aforo: int | None = None) -> DisponibilidadCupo:
    return DisponibilidadCupo.abrir(uuid4(), date(2026, 11, 5), totales, aforo=aforo)


def test_abrir_deja_todos_los_cupos_disponibles():
    d = dia(10)
    assert (d.cupos_totales, d.cupos_disponibles, d.cupos_reservados) == (10, 10, 0)


@pytest.mark.parametrize("totales", [0, -1])
def test_abrir_exige_al_menos_un_cupo(totales):
    with pytest.raises(Validacion):
        dia(totales)


def test_abrir_respeta_el_aforo():
    with pytest.raises(SuperaAforo):
        dia(30, aforo=20)


def test_descontar_y_liberar():
    d = dia(10)
    d.descontar(4)
    assert d.cupos_disponibles == 6
    d.liberar(4)
    assert d.cupos_disponibles == 10


def test_descontar_mas_de_lo_disponible():
    d = dia(3)
    with pytest.raises(CuposInsuficientes):
        d.descontar(4)
    assert d.cupos_disponibles == 3


def test_liberar_mas_de_lo_reservado_es_un_error_de_programacion():
    d = dia(10)
    d.descontar(2)
    with pytest.raises(ValueError):
        d.liberar(3)


def test_solo_los_cambios_del_prestador_suben_la_version():
    d = dia(10)
    d.descontar(1)
    d.liberar(1)
    assert d.version == 1
    d.ajustar(12, None)
    assert d.version == 2


class TestAjustar:
    def test_conserva_lo_reservado(self):
        d = dia(10)
        d.descontar(4)
        d.ajustar(20, Decimal("85000"))
        assert (d.cupos_totales, d.cupos_disponibles, d.tarifa_dia) == (20, 16, Decimal("85000"))

    def test_no_baja_de_lo_reservado(self):
        d = dia(10)
        d.descontar(6)
        with pytest.raises(CuposComprometidos):
            d.ajustar(5, None)

    def test_cerrar_el_dia_es_dejar_solo_lo_reservado(self):
        d = dia(10)
        d.descontar(6)
        d.ajustar(6, None)
        assert d.cupos_disponibles == 0

    def test_respeta_el_aforo(self):
        d = dia(10)
        with pytest.raises(SuperaAforo):
            d.ajustar(25, None, aforo=20)

    def test_tarifa_negativa(self):
        with pytest.raises(Validacion):
            dia(10).ajustar(10, Decimal("-1"))


class TestSecuencia:
    """`secuencia` sube con cada cambio; `version` (ETag) solo con las ediciones del prestador."""

    def test_cada_cambio_sube_la_secuencia(self):
        d = dia(10)
        d.descontar(3)
        d.liberar(1)
        d.ajustar(12, None)
        assert (d.secuencia, d.version) == (4, 2)

    def test_un_cambio_rechazado_no_sube_la_secuencia(self):
        d = dia(3)
        with pytest.raises(CuposInsuficientes):
            d.descontar(4)
        assert d.secuencia == 1

    def test_el_evento_lleva_el_estado_completo_y_la_secuencia_como_version(self):
        d = dia(10)
        d.descontar(4)
        evento = d.evento()
        assert evento.tipo == "disponibilidad.actualizada"
        assert evento.payload == {
            "servicio_id": str(d.servicio_id), "fecha": "2026-11-05",
            "cupos_totales": 10, "cupos_disponibles": 6, "version": 2,
        }
