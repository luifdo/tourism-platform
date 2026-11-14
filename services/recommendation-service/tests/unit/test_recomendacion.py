from uuid import uuid4

import pytest

from src.domain.recomendacion import Recomendacion, RecomendacionSinJustificacionError


def test_recomendacion_con_justificacion():
    recomendacion = Recomendacion(
        servicio_id=uuid4(),
        nombre="Buceo en Taganga",
        justificacion="Baja presión de capacidad y buenas reseñas.",
    )

    assert recomendacion.justificacion.startswith("Baja presión")


@pytest.mark.parametrize("justificacion", ["", "   ", "\n"])
def test_recomendacion_sin_justificacion_se_rechaza(justificacion):
    with pytest.raises(RecomendacionSinJustificacionError):
        Recomendacion(servicio_id=uuid4(), nombre="Buceo en Taganga", justificacion=justificacion)
