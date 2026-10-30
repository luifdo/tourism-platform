from decimal import Decimal
from uuid import uuid4

import pytest

from domain.errores import NoDisponible
from domain.servicio import ServicioRef

def servicio(version: int = 1, activo: bool = True) -> ServicioRef:
    return ServicioRef(uuid4(), uuid4(), uuid4(), 20, Decimal("50000"), activo, version)


class TestServicioRef:
    def test_es_de_compara_con_el_usuario_no_con_el_perfil(self):
        s = servicio()
        assert s.es_de(s.prestador_usuario_id)
        assert not s.es_de(s.prestador_id)

    def test_inactivo(self):
        with pytest.raises(NoDisponible):
            servicio(activo=False).exigir_activo()

    @pytest.mark.parametrize(("nueva", "actual", "reemplaza"), [(2, 1, True), (1, 1, False), (1, 2, False)])
    def test_solo_reemplaza_versiones_mas_nuevas(self, nueva, actual, reemplaza):
        assert servicio(version=nueva).reemplaza_a(servicio(version=actual)) is reemplaza

    def test_reemplaza_si_no_habia_nada(self):
        assert servicio().reemplaza_a(None)

