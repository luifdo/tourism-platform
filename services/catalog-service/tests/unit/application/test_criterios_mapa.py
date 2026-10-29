import pytest

from app.application.dto.criterios_mapa_servicios import CriteriosMapaServicios
from app.application.dto.escala_mapa import EscalaMapa
from app.domain.errors import DatoInvalido
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.geo import Bbox

SANTA_MARTA = Bbox(min_lon=-74.25, min_lat=11.10, max_lon=-74.05, max_lat=11.35)


class TestEscala:
    @pytest.mark.parametrize("zoom", [-1, 20])
    def test_zoom_fuera_de_leaflet(self, zoom: int) -> None:
        with pytest.raises(DatoInvalido) as exc:
            EscalaMapa(zoom)
        assert exc.value.detalle == {"campo": "zoom", "regla": "rango", "minimo": 0, "maximo": 19}

    def test_agrupa_por_debajo_de_13(self) -> None:
        assert EscalaMapa(12).agrupa and not EscalaMapa(13).agrupa

    def test_un_pixel_de_tesela_osm(self) -> None:
        # A zoom 0 el mundo (360°) mide 256 px.
        assert EscalaMapa(0).grados_por_pixel == 360 / 256
        assert EscalaMapa(0).tolerancia_grados == 360 / 256

    def test_cada_zoom_divide_la_celda_a_la_mitad(self) -> None:
        assert EscalaMapa(10).celda_grados == pytest.approx(2 * EscalaMapa(11).celda_grados)
        # A zoom 12, una celda de 64 px son unos 2,5 km en Santa Marta.
        assert EscalaMapa(12).celda_grados * 111_000 == pytest.approx(2_440, rel=0.05)


class TestCriterios:
    def test_al_agrupar_la_vista_se_alinea_a_las_celdas(self) -> None:
        escala = EscalaMapa(10)
        criterios = CriteriosMapaServicios(vista=SANTA_MARTA, escala=escala)
        celda = escala.celda_grados
        vista = criterios.vista
        for valor in (vista.min_lon, vista.min_lat, vista.max_lon, vista.max_lat):
            assert valor / celda == pytest.approx(round(valor / celda), abs=1e-6)
        assert vista.min_lon <= SANTA_MARTA.min_lon and vista.max_lat >= SANTA_MARTA.max_lat

    def test_vistas_casi_iguales_comparten_criterios(self) -> None:
        corrida = Bbox(min_lon=-74.2499, min_lat=11.1001, max_lon=-74.0501, max_lat=11.3499)
        escala = EscalaMapa(9)
        assert CriteriosMapaServicios(SANTA_MARTA, escala) == CriteriosMapaServicios(
            corrida, escala
        )

    def test_sin_agrupar_la_vista_queda_igual(self) -> None:
        assert CriteriosMapaServicios(SANTA_MARTA, EscalaMapa(15)).vista == SANTA_MARTA

    def test_la_vista_alineada_no_sale_del_mundo(self) -> None:
        mundo = Bbox(min_lon=-180, min_lat=-85, max_lon=180, max_lat=85)
        vista = CriteriosMapaServicios(mundo, EscalaMapa(1)).vista
        assert (vista.min_lon, vista.max_lon) == (-180, 180)
        assert vista.min_lat >= -90 and vista.max_lat <= 90

    def test_categorias_ordenadas_y_sin_repetir(self) -> None:
        criterios = CriteriosMapaServicios(
            SANTA_MARTA,
            EscalaMapa(14),
            categorias=(Categoria.PLAYA, Categoria.CULTURA, Categoria.PLAYA),
        )
        assert criterios.categorias == (Categoria.CULTURA, Categoria.PLAYA)
