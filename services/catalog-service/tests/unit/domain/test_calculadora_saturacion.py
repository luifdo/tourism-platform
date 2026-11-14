from app.domain.services.calculadora_saturacion import CalculadoraSaturacion, CargaServicio
from app.domain.value_objects.saturacion import NivelSaturacion

calc = CalculadoraSaturacion()


def test_servicio_al_85_por_ciento_tiene_bandera() -> None:
    r = calc.de_servicio(CargaServicio(personas_activas=17, capacidad_aforo_diario=20, activo=True))
    assert r is not None
    assert (r.indice, r.nivel, r.bandera) == (0.85, NivelSaturacion.ALTO, True)


def test_sobrecupo_supera_1() -> None:
    r = calc.de_servicio(CargaServicio(personas_activas=30, capacidad_aforo_diario=20, activo=True))
    assert r is not None and r.indice == 1.5


def test_sin_capacidad_no_hay_indice() -> None:
    assert calc.de_zona([]) is None


def test_zona_suma_activos_y_desactivados_con_reservas() -> None:
    r = calc.de_zona(
        [
            CargaServicio(personas_activas=10, capacidad_aforo_diario=20, activo=True),
            CargaServicio(personas_activas=0, capacidad_aforo_diario=30, activo=True),
            # desactivado hoy pero con reservas vigentes: sigue recibiendo personas
            CargaServicio(personas_activas=5, capacidad_aforo_diario=10, activo=False),
            # desactivado y sin reservas: no infla la capacidad
            CargaServicio(personas_activas=0, capacidad_aforo_diario=100, activo=False),
        ]
    )
    assert r is not None
    assert (r.personas_activas, r.capacidad, r.indice) == (15, 60, 0.25)
    assert r.nivel is NivelSaturacion.BAJO and not r.bandera
