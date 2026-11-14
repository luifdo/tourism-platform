from datetime import timedelta
from uuid import uuid4

import pytest

from app.domain.entities.reporte_resena import ReporteResena
from app.domain.errors import DatoInvalido, DemasiadosReportes
from app.domain.services.limite_reportes import LIMITE_POR_HORA, LimiteReportes
from app.domain.value_objects.identidad import Rol
from app.domain.value_objects.motivo_reporte import MotivoReporte
from tests.unit.domain.comun import AHORA


def crear(motivo: MotivoReporte, detalle: str | None) -> ReporteResena:
    return ReporteResena.crear(uuid4(), uuid4(), Rol.TURISTA, motivo, detalle, False, AHORA)


class TestReporte:
    def test_otro_exige_detalle(self) -> None:
        with pytest.raises(DatoInvalido) as error:
            crear(MotivoReporte.OTRO, "   ")
        assert error.value.detalle["regla"] == "requiere"

    def test_detalle_limpio_y_maximo(self) -> None:
        assert crear(MotivoReporte.OTRO, " Publicidad ").detalle == "Publicidad"
        assert crear(MotivoReporte.SPAM, "").detalle is None
        with pytest.raises(DatoInvalido):
            crear(MotivoReporte.SPAM, "x" * 501)

    def test_se_resuelve_una_vez(self) -> None:
        r = crear(MotivoReporte.FALSO, None)
        assert r.abierto
        r.resolver(AHORA)
        r.resolver(AHORA + timedelta(days=1))
        assert r.resuelto_en == AHORA


class TestLimiteReportes:
    def test_por_debajo_del_limite(self) -> None:
        recientes = [AHORA - timedelta(minutes=m) for m in range(LIMITE_POR_HORA - 1)]
        LimiteReportes().exigir(recientes, AHORA)

    def test_los_de_hace_mas_de_una_hora_no_cuentan(self) -> None:
        viejos = [AHORA - timedelta(hours=1, minutes=m) for m in range(20)]
        LimiteReportes().exigir(viejos, AHORA)

    def test_en_el_limite_dice_cuanto_esperar(self) -> None:
        # El más antiguo de los 10 fue hace 50 minutos: se libera en 10.
        recientes = [AHORA - timedelta(minutes=50 - m) for m in range(LIMITE_POR_HORA)]
        with pytest.raises(DemasiadosReportes) as error:
            LimiteReportes().exigir(recientes, AHORA)
        assert error.value.retry_after == 600
