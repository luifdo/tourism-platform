from decimal import Decimal

import pytest

from app.application.dto.criterios_busqueda import CriteriosBusqueda, OrdenBusqueda
from app.domain.errors import DatoInvalido
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.idioma import Idioma


def test_normaliza_texto_y_categorias() -> None:
    criterios = CriteriosBusqueda(
        idioma=Idioma.ES,
        texto="   ",
        categorias=(Categoria.PLAYA, Categoria.CULTURA, Categoria.PLAYA),
    )
    assert criterios.texto is None
    assert criterios.categorias == (Categoria.CULTURA, Categoria.PLAYA)


def test_mismos_filtros_en_otro_orden_son_iguales() -> None:
    """Importa para la caché: misma búsqueda, misma clave."""
    a = CriteriosBusqueda(idioma=Idioma.ES, categorias=(Categoria.PLAYA, Categoria.CULTURA))
    b = CriteriosBusqueda(idioma=Idioma.ES, categorias=(Categoria.CULTURA, Categoria.PLAYA))
    assert a == b


@pytest.mark.parametrize(
    "cambios",
    [
        {"pagina": 0},
        {"tamano": 101},
        {"radio_m": 99},
        {"radio_m": 50001},
        {"precio_min": Decimal("10"), "precio_max": Decimal("5")},
        {"orden": OrdenBusqueda.DISTANCIA},
        {"orden": OrdenBusqueda.RELEVANCIA},
    ],
    ids=[
        "pagina_cero",
        "tamano_grande",
        "radio_chico",
        "radio_grande",
        "precios_invertidos",
        "distancia_sin_punto",
        "relevancia_sin_texto",
    ],
)
def test_criterios_invalidos(cambios: dict) -> None:
    with pytest.raises(DatoInvalido):
        CriteriosBusqueda(idioma=Idioma.ES, **cambios)


def test_orden_valido_con_sus_requisitos() -> None:
    CriteriosBusqueda(
        idioma=Idioma.EN, orden=OrdenBusqueda.DISTANCIA, cerca_de=Coordenada(11.2, -74.2)
    )
    CriteriosBusqueda(idioma=Idioma.EN, orden=OrdenBusqueda.RELEVANCIA, texto="beach")
