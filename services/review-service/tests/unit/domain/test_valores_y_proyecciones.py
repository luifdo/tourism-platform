from datetime import date
from uuid import uuid4

import pytest

from app.domain.errors import DatoInvalido
from app.domain.value_objects.aspecto import Aspecto
from app.domain.value_objects.contenido_resena import ContenidoResena
from tests.unit.domain.comun import DUENO, dueno, elegibilidad


class TestContenidoResena:
    @pytest.mark.parametrize("puntuacion", [0, 6, True])
    def test_puntuacion_de_1_a_5(self, puntuacion: int) -> None:
        with pytest.raises(DatoInvalido):
            ContenidoResena(puntuacion)

    def test_aspecto_fuera_de_rango_dice_cual(self) -> None:
        with pytest.raises(DatoInvalido) as error:
            ContenidoResena(4, {Aspecto.LIMPIEZA: 5, Aspecto.GUIANZA: 9})
        assert error.value.detalle["campo"] == "aspectos.GUIANZA"

    def test_comentario_limpio(self) -> None:
        assert ContenidoResena(4, comentario="  Muy bueno ").comentario == "Muy bueno"
        assert ContenidoResena(4, comentario="   ").comentario is None
        with pytest.raises(DatoInvalido):
            ContenidoResena(4, comentario="x" * 2001)

    def test_no_comparte_el_diccionario_de_aspectos(self) -> None:
        aspectos = {Aspecto.ATENCION: 5}
        contenido = ContenidoResena(5, aspectos)
        aspectos[Aspecto.LIMPIEZA] = 1
        assert contenido.aspectos == {Aspecto.ATENCION: 5}


class TestElegibilidad:
    def test_se_queda_con_la_visita_mas_reciente(self) -> None:
        e = elegibilidad(date(2026, 11, 14))
        assert e.registrar_visita(date(2026, 10, 1)) is False
        assert e.registrar_visita(date(2026, 11, 14)) is False
        assert e.registrar_visita(date(2026, 12, 2)) is True
        assert e.ultima_visita == date(2026, 12, 2)


class TestServicioDueno:
    def test_descarta_versiones_viejas(self) -> None:
        d = dueno()
        otro = uuid4()
        assert d.aplicar(1, otro) is False
        assert d.es_dueno(DUENO)
        assert d.aplicar(2, otro) is True
        assert d.es_dueno(otro) and not d.es_dueno(DUENO)
