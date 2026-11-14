from datetime import date, datetime, timedelta

import pytest

from domain import reglas
from domain.errores import Validacion
from domain.reglas import ZONA


def bogota(*args) -> datetime:
    return datetime(*args, tzinfo=ZONA)


class TestValidarFechaSolicitud:
    def test_acepta_manana(self):
        reglas.validar_fecha_solicitud(date(2026, 11, 6), bogota(2026, 11, 5, 23, 0))

    @pytest.mark.parametrize("fecha", [date(2026, 11, 5), date(2026, 11, 4)])
    def test_rechaza_hoy_y_pasado(self, fecha):
        with pytest.raises(Validacion):
            reglas.validar_fecha_solicitud(fecha, bogota(2026, 11, 5, 8, 0))

    def test_usa_la_fecha_de_bogota_no_la_utc(self):
        # 2026-11-06 03:00 UTC sigue siendo 5 de noviembre en Bogotá (UTC-5).
        ahora_utc = datetime.fromisoformat("2026-11-06T03:00:00+00:00")
        reglas.validar_fecha_solicitud(date(2026, 11, 6), ahora_utc)


class TestCalcularExpiraEn:
    def test_reserva_lejana_tiene_48_horas(self):
        ahora = bogota(2026, 11, 1, 10, 0)
        assert reglas.calcular_expira_en(date(2026, 11, 20), ahora) == ahora + timedelta(hours=48)

    def test_reserva_para_manana_vence_a_medianoche(self):
        ahora = bogota(2026, 11, 5, 10, 0)
        assert reglas.calcular_expira_en(date(2026, 11, 6), ahora) == bogota(2026, 11, 6, 0, 0)

    def test_reserva_para_pasado_manana_vence_al_inicio_de_ese_dia(self):
        ahora = bogota(2026, 11, 5, 10, 0)
        assert reglas.calcular_expira_en(date(2026, 11, 7), ahora) == bogota(2026, 11, 7, 0, 0)

    def test_plazo_configurable(self):
        ahora = bogota(2026, 11, 1, 10, 0)
        assert reglas.calcular_expira_en(date(2026, 11, 20), ahora, 24) == ahora + timedelta(hours=24)


class TestCancelacionTurista:
    def test_puede_hasta_el_dia_anterior(self):
        assert reglas.turista_puede_cancelar_confirmada(date(2026, 11, 6), bogota(2026, 11, 5, 23, 59))

    def test_no_puede_el_mismo_dia(self):
        assert not reglas.turista_puede_cancelar_confirmada(date(2026, 11, 6), bogota(2026, 11, 6, 0, 0))
