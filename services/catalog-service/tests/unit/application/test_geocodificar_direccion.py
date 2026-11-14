"""GeocodificarDireccion: el rango del contrato se valida sobre lo recibido."""

from uuid import uuid4

import pytest

from app.application.dto.candidato_direccion import CandidatoDireccion
from app.application.use_cases.geocodificar_direccion import GeocodificarDireccion
from app.domain.errors import DatoInvalido
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.idioma import Idioma

PRESTADOR = Identidad(uuid4(), Rol.PRESTADOR)
CANDIDATO = CandidatoDireccion(ubicacion=Coordenada(lat=11.24, lon=-74.21), etiqueta="Santa Marta")


class GeocodificadorFalso:
    def __init__(self) -> None:
        self.consultas: list[str] = []

    async def buscar(self, direccion: str, idioma: Idioma) -> list[CandidatoDireccion]:
        self.consultas.append(direccion)
        return [CANDIDATO]


async def test_junta_los_espacios_antes_de_buscar() -> None:
    falso = GeocodificadorFalso()
    candidatos = await GeocodificarDireccion(falso).execute(
        PRESTADOR, "  Calle 22\n #3-45 ", Idioma.ES
    )
    assert candidatos == [CANDIDATO]
    assert falso.consultas == ["Calle 22 #3-45"]


async def test_casi_todo_espacios_no_es_error_sino_sin_sugerencias() -> None:
    # Lo que encontró schemathesis: 5 caracteres válidos para el contrato, pero \x1d y \r son
    # espacios para Python y quedan 3. Antes respondía 400 a una petición válida.
    falso = GeocodificadorFalso()
    candidatos = await GeocodificarDireccion(falso).execute(
        PRESTADOR, "\U000f5759\x1d\xdb\xa2\r", Idioma.ES
    )
    assert candidatos == []
    assert falso.consultas == []  # no gasta el cupo de Nominatim


@pytest.mark.parametrize("direccion", ["abcd", "x" * 201])
async def test_fuera_del_rango_del_contrato_es_invalido(direccion: str) -> None:
    with pytest.raises(DatoInvalido):
        await GeocodificarDireccion(GeocodificadorFalso()).execute(PRESTADOR, direccion, Idioma.ES)
