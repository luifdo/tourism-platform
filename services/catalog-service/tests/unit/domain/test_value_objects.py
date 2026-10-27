from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.errors import DatoInvalido, RolNoPermitido
from app.domain.value_objects.catalogos import EstadoReserva
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.geo import Bbox, Coordenada, PoligonoGeoJSON
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.saturacion import NivelSaturacion
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido

CUADRADO = [[[-74.2, 11.1], [-74.1, 11.1], [-74.1, 11.2], [-74.2, 11.2], [-74.2, 11.1]]]


class TestIdioma:
    @pytest.mark.parametrize(
        ("cabecera", "esperado"),
        [
            (None, Idioma.ES),
            ("", Idioma.ES),
            ("en", Idioma.EN),
            ("en-US,en;q=0.9,es;q=0.8", Idioma.EN),
            ("es-CO,es;q=0.9", Idioma.ES),
            ("fr", Idioma.ES),
        ],
    )
    def test_desde_accept_language(self, cabecera: str | None, esperado: Idioma) -> None:
        assert Idioma.desde_accept_language(cabecera) is esperado


class TestTextoTraducido:
    def test_devuelve_ingles_si_existe(self) -> None:
        texto = TextoTraducido(es="Playa", en="Beach")
        assert texto.en_idioma(Idioma.EN) == ("Beach", Idioma.EN)

    def test_cae_al_espanol_si_falta_el_ingles(self) -> None:
        texto = TextoTraducido(es="Playa")
        assert texto.en_idioma(Idioma.EN) == ("Playa", Idioma.ES)

    def test_espanol_obligatorio(self) -> None:
        with pytest.raises(DatoInvalido):
            TextoTraducido(es="   ", en="Beach")

    def test_recorta_espacios_y_ingles_vacio_es_none(self) -> None:
        texto = TextoTraducido(es="  Playa ", en="  ")
        assert texto == TextoTraducido(es="Playa")
        assert texto.a_dict() == {"es": "Playa"}


class TestGeo:
    def test_coordenada_fuera_de_rango(self) -> None:
        with pytest.raises(DatoInvalido):
            Coordenada(lat=91, lon=0)
        with pytest.raises(DatoInvalido):
            Coordenada(lat=0, lon=-181)

    def test_bbox_valida_orden(self) -> None:
        assert Bbox.desde_lista([-74.3, 11.0, -74.0, 11.3]).max_lat == 11.3
        with pytest.raises(DatoInvalido):
            Bbox.desde_lista([-74.0, 11.0, -74.3, 11.3])
        with pytest.raises(DatoInvalido):
            Bbox.desde_lista([-74.0, 11.0])

    def test_poligono_se_normaliza_a_multipoligono(self) -> None:
        poligono = PoligonoGeoJSON.desde_geojson({"type": "Polygon", "coordinates": CUADRADO})
        assert poligono.a_geojson() == {"type": "MultiPolygon", "coordinates": [CUADRADO]}

    def test_polygon_y_multipolygon_equivalentes_son_iguales(self) -> None:
        assert PoligonoGeoJSON.desde_geojson(
            {"type": "Polygon", "coordinates": CUADRADO}
        ) == PoligonoGeoJSON.desde_geojson({"type": "MultiPolygon", "coordinates": [CUADRADO]})

    @pytest.mark.parametrize(
        "geometria",
        [
            {"type": "Point", "coordinates": [-74.2, 11.1]},
            {"type": "Polygon", "coordinates": [[[-74.2, 11.1], [-74.1, 11.1], [-74.2, 11.1]]]},
            {
                "type": "Polygon",
                "coordinates": [[[-74.2, 11.1], [-74.1, 11.1], [-74.1, 11.2], [-74.2, 11.2]]],
            },
            {
                "type": "Polygon",
                "coordinates": [[[11.1, -200], [11.1, -74.1], [11.2, -74.1], [11.1, -200]]],
            },
            {"type": "MultiPolygon", "coordinates": []},
            {"type": "Polygon"},
        ],
        ids=[
            "no_poligonal",
            "pocos_puntos",
            "anillo_abierto",
            "lat_lon_invertidos",
            "multi_vacio",
            "sin_coordenadas",
        ],
    )
    def test_poligono_invalido(self, geometria: dict) -> None:
        with pytest.raises(DatoInvalido):
            PoligonoGeoJSON.desde_geojson(geometria)


class TestCodigoZona:
    @pytest.mark.parametrize("codigo", ["minca", "centro-historico", "el-rodadero-2"])
    def test_validos(self, codigo: str) -> None:
        assert str(CodigoZona(codigo)) == codigo

    @pytest.mark.parametrize("codigo", ["M", "Minca", "centro histórico", "x" * 41])
    def test_invalidos(self, codigo: str) -> None:
        with pytest.raises(DatoInvalido):
            CodigoZona(codigo)


class TestTarifa:
    def test_redondea_a_centavos(self) -> None:
        assert Tarifa(Decimal("85000.005")).valor == Decimal("85000.00")

    @pytest.mark.parametrize("valor", [Decimal("-1"), Decimal("10000000000"), "abc"])
    def test_invalidas(self, valor: object) -> None:
        with pytest.raises(DatoInvalido):
            Tarifa(valor)  # type: ignore[arg-type]


class TestNivelSaturacion:
    @pytest.mark.parametrize(
        ("indice", "nivel"),
        [
            (0.0, NivelSaturacion.BAJO),
            (0.5999, NivelSaturacion.BAJO),
            (0.60, NivelSaturacion.MEDIO),
            (0.8499, NivelSaturacion.MEDIO),
            (0.85, NivelSaturacion.ALTO),
            (1.3, NivelSaturacion.ALTO),
        ],
    )
    def test_cortes(self, indice: float, nivel: NivelSaturacion) -> None:
        assert NivelSaturacion.desde_indice(indice) is nivel


class TestEstadoReserva:
    def test_activas_son_solicitada_y_confirmada(self) -> None:
        activas = {e for e in EstadoReserva if e.activa}
        assert activas == {EstadoReserva.SOLICITADA, EstadoReserva.CONFIRMADA}


class TestIdentidad:
    def test_rol_permitido(self) -> None:
        Identidad(uuid4(), Rol.ENTIDAD).exigir_rol(Rol.ENTIDAD, Rol.ADMIN)

    def test_rol_no_permitido(self) -> None:
        with pytest.raises(RolNoPermitido) as error:
            Identidad(uuid4(), Rol.TURISTA).exigir_rol(Rol.ENTIDAD, Rol.ADMIN)
        assert error.value.codigo == "ROL_NO_PERMITIDO"

    def test_valores_de_cabecera(self) -> None:
        assert Rol("Prestador") is Rol.PRESTADOR
