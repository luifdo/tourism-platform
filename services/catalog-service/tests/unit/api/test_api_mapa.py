"""Capas GeoJSON del mapa con un doble de la consulta: formato RFC 7946, idioma y errores."""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_consulta_mapa
from app.application.dto.alerta_en_mapa import AlertaEnMapa
from app.application.dto.alerta_vista import AlertaVista
from app.application.dto.criterios_mapa_servicios import CriteriosMapaServicios
from app.application.dto.escala_mapa import EscalaMapa
from app.application.dto.grupo_en_mapa import GrupoEnMapa
from app.application.dto.mapa_servicios import MapaServicios
from app.application.dto.servicio_en_mapa import ServicioEnMapa
from app.application.dto.zona_en_mapa import ZonaEnMapa
from app.application.dto.zona_resumen import ZonaResumen
from app.domain.value_objects.catalogos import Categoria, NivelAlerta
from app.domain.value_objects.geo import Bbox, Coordenada
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.main import create_app

BBOX = "-74.25,11.10,-74.05,11.35"
CAFE = ServicioEnMapa(
    id=uuid4(),
    nombre=TextoTraducido(es="Tour del café", en="Coffee tour"),
    categoria=Categoria.GASTRONOMIA,
    ubicacion=Coordenada(lat=11.1426, lon=-74.1178),
    calificacion_promedio=4.5,
)
POLIGONO = {
    "type": "MultiPolygon",
    "coordinates": [[[[-74.13, 11.13], [-74.10, 11.13], [-74.10, 11.16], [-74.13, 11.13]]]],
}
MINCA = ZonaResumen(codigo="minca", nombre=TextoTraducido(es="Minca"))


def alerta(servicio: bool) -> AlertaEnMapa:
    vista = AlertaVista(
        id=uuid4(),
        nivel=NivelAlerta.PREVENTIVA,
        mensaje=TextoTraducido(es="Lluvias fuertes", en="Heavy rain"),
        servicio_id=CAFE.id if servicio else None,
        zona=None if servicio else MINCA,
        fecha_expiracion=datetime(2026, 10, 20, tzinfo=UTC),
    )
    geometria = {"type": "Point", "coordinates": [-74.1178, 11.1426]} if servicio else POLIGONO
    return AlertaEnMapa(alerta=vista, geometria=geometria)


class MapaFalso:
    def __init__(self) -> None:
        self.criterios: CriteriosMapaServicios | None = None
        self.vista: Bbox | None = None
        self.escala: EscalaMapa | None = None

    async def servicios(self, criterios: CriteriosMapaServicios) -> MapaServicios:
        self.criterios = criterios
        grupo = GrupoEnMapa(ubicacion=Coordenada(lat=11.24, lon=-74.21), conteo=12)
        return MapaServicios(servicios=(CAFE,), grupos=(grupo,))

    async def zonas(self, vista: Bbox | None, escala: EscalaMapa) -> list[ZonaEnMapa]:
        self.vista, self.escala = vista, escala
        nombre = TextoTraducido(es="Parque Tayrona", en="Tayrona Park")
        return [ZonaEnMapa(id=uuid4(), codigo="parque-tayrona", nombre=nombre, geometria=POLIGONO)]

    async def alertas(self, ahora: datetime, vista: Bbox | None) -> list[AlertaEnMapa]:
        self.vista = vista
        return [alerta(servicio=True), alerta(servicio=False)]


@pytest.fixture
def mapa() -> MapaFalso:
    return MapaFalso()


@pytest.fixture
def cliente(mapa: MapaFalso) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_consulta_mapa] = lambda: mapa
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestServicios:
    def test_feature_collection_en_lon_lat(self, cliente: TestClient) -> None:
        r = cliente.get("/api/catalog/mapa/servicios", params={"bbox": BBOX, "zoom": 11})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/geo+json"
        cuerpo = r.json()
        assert cuerpo["type"] == "FeatureCollection"
        servicio, grupo = cuerpo["features"]
        assert servicio["type"] == "Feature"
        assert servicio["geometry"] == {"type": "Point", "coordinates": [-74.1178, 11.1426]}
        assert servicio["properties"] == {
            "tipo": "servicio",
            "id": str(CAFE.id),
            "nombre": "Tour del café",
            "categoria": "GASTRONOMIA",
            "categoria_etiqueta": "Gastronomía",
            "calificacion_promedio": 4.5,
        }
        assert grupo["geometry"]["coordinates"] == [-74.21, 11.24]
        assert grupo["properties"] == {"tipo": "grupo", "conteo": 12}

    def test_en_ingles(self, cliente: TestClient) -> None:
        r = cliente.get(
            "/api/catalog/mapa/servicios",
            params={"bbox": BBOX, "zoom": 14},
            headers={"Accept-Language": "en"},
        )
        assert r.headers["content-language"] == "en"
        propiedades = r.json()["features"][0]["properties"]
        assert (propiedades["nombre"], propiedades["categoria_etiqueta"]) == (
            "Coffee tour",
            "Food & dining",
        )

    def test_filtros_llegan_validados(self, cliente: TestClient, mapa: MapaFalso) -> None:
        cliente.get(
            "/api/catalog/mapa/servicios",
            params={
                "bbox": BBOX,
                "zoom": 15,
                "categoria": "playa,cultura",
                "zona": "taganga",
                "tipo": "ACCESO_PLAYA",
                "mascotas": "true",
                "acepta_pago_digital": "false",
            },
        )
        c = mapa.criterios
        assert c is not None
        assert c.vista == Bbox(-74.25, 11.10, -74.05, 11.35) and c.escala == EscalaMapa(15)
        assert (c.categorias, c.zona) == ((Categoria.CULTURA, Categoria.PLAYA), "taganga")
        assert c.filtros.filtro_atributos() == {
            "comunes": {"mascotas": True},
            "pagos": {"acepta_pago_digital": False},
        }
        assert [t.value for t in c.filtros.tipos] == ["ACCESO_PLAYA"]


class TestZonasYAlertas:
    def test_zonas_con_su_poligono(self, cliente: TestClient, mapa: MapaFalso) -> None:
        r = cliente.get("/api/catalog/mapa/zonas", params={"zoom": 10})
        assert r.headers["content-type"] == "application/geo+json"
        [zona] = r.json()["features"]
        assert zona["geometry"] == POLIGONO
        assert zona["properties"]["nombre"] == "Parque Tayrona"
        assert mapa.vista is None and mapa.escala == EscalaMapa(10)

    def test_alertas_punto_y_poligono(self, cliente: TestClient) -> None:
        r = cliente.get(
            "/api/catalog/mapa/alertas", params={"bbox": BBOX}, headers={"Accept-Language": "en"}
        )
        de_servicio, de_zona = r.json()["features"]
        assert de_servicio["geometry"]["type"] == "Point"
        assert de_zona["geometry"]["type"] == "MultiPolygon"
        assert de_servicio["properties"]["servicio_id"] == str(CAFE.id)
        assert de_zona["properties"]["zona"] == "minca"
        assert (de_zona["properties"]["nivel_etiqueta"], de_zona["properties"]["mensaje"]) == (
            "Advisory",
            "Heavy rain",
        )


class TestErrores:
    @pytest.mark.parametrize(
        ("params", "idioma", "mensaje"),
        [
            ({"zoom": 10}, "es", "El campo «bbox» es obligatorio."),
            ({"bbox": BBOX}, "en", "The field 'zoom' is required."),
            (
                {"bbox": "-74.25,11.10,-74.05", "zoom": 10},
                "es",
                "«bbox» debe tener cuatro valores: minLon,minLat,maxLon,maxLat.",
            ),
            (
                {"bbox": "-74.05,11.10,-74.25,11.35", "zoom": 10},
                "en",
                "In 'bbox' the minimums must be lower than the maximums.",
            ),
            ({"bbox": "a,b,c,d", "zoom": 10}, "es", "El campo «bbox» debe ser un número."),
            (
                {"bbox": "-74.25,95,-74.05,96", "zoom": 10},
                "en",
                "The field 'lat' must be between -90 and 90.",
            ),
            ({"bbox": BBOX, "zoom": 20}, "es", "El campo «zoom» no tiene un formato válido."),
        ],
    )
    def test_validacion_en_el_idioma_pedido(
        self, cliente: TestClient, params: dict, idioma: str, mensaje: str
    ) -> None:
        r = cliente.get(
            "/api/catalog/mapa/servicios", params=params, headers={"Accept-Language": idioma}
        )
        assert r.status_code == 400
        assert r.json()["error"] == "VALIDACION" and r.json()["message"] == mensaje
