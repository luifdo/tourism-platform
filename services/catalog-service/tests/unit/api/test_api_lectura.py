"""API de lectura con dobles de las consultas: contrato HTTP, idioma y formato de errores."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_consulta_alertas, get_consulta_servicios, get_consulta_zonas
from app.application.dto.alerta_vista import AlertaVista
from app.application.dto.criterios_busqueda import CriteriosBusqueda, OrdenBusqueda
from app.application.dto.pagina_servicios import PaginaServicios
from app.application.dto.prestador_publico import PrestadorPublico
from app.application.dto.servicio_detalle import ServicioDetalle
from app.application.dto.servicio_resumen import ServicioResumen
from app.application.dto.zona_resumen import ZonaResumen
from app.application.dto.zona_vista import ZonaVista
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_experiencia import BloqueExperiencia
from app.domain.value_objects.atributos.bloque_pagos import BloquePagos
from app.domain.value_objects.atributos.cajeros_cercanos import CajerosCercanos
from app.domain.value_objects.atributos.credito_prestador import CreditoPrestador
from app.domain.value_objects.atributos.valores import (
    MedioPago,
    NivelFisico,
    OpcionDietaria,
    RecomendacionDinero,
    SenalInternet,
)
from app.domain.value_objects.catalogos import Categoria, NivelAlerta, UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.main import create_app

SERVICIO_ID = uuid4()
MINCA = ZonaResumen(codigo="minca", nombre=TextoTraducido(es="Minca"))
TAYRONA = ZonaResumen(
    codigo="parque-tayrona",
    nombre=TextoTraducido(es="Parque Nacional Natural Tayrona", en="Tayrona National Natural Park"),
)
SERVICIO = ServicioResumen(
    id=SERVICIO_ID,
    nombre=TextoTraducido(es="Tour del café", en="Coffee tour"),
    tipo=TipoServicio.EXPERIENCIA_GASTRONOMICA,
    categoria=Categoria.GASTRONOMIA,
    ubicacion=Coordenada(lat=11.1426, lon=-74.1178),
    tarifa_base=Decimal("85000.50"),
    unidad_tarifa=UnidadTarifa.POR_PERSONA,
    zona=MINCA,
    calificacion_promedio=4.5,
    total_resenas=2,
    imagen_principal=None,
)
ALERTA = AlertaVista(
    id=uuid4(),
    nivel=NivelAlerta.CRITICA,
    mensaje=TextoTraducido(es="Sendero cerrado"),  # sin traducción: sale en español
    servicio_id=None,
    zona=MINCA,
    fecha_expiracion=datetime(2026, 10, 20, tzinfo=UTC),
)


ATRIBUTOS = AtributosServicio(
    experiencia=BloqueExperiencia(
        duracion_minutos=180,
        nivel_fisico=NivelFisico.MEDIO,
        punto_encuentro=TextoTraducido(es="Parque de Minca", en="Minca park"),
    ),
    pagos=BloquePagos(
        senal_internet=SenalInternet.SIN_SENAL,
        medios_pago=(MedioPago.EFECTIVO,),
        recomendacion_dinero=RecomendacionDinero.EFECTIVO,
        credito=CreditoPrestador(ofrece=True, plazo_dias=3),
        cajeros=CajerosCercanos(
            hay_cerca=False,
            referencia=TextoTraducido(es="Parque de Minca", en="Minca park"),
            distancia_km=8,
        ),
    ),
)


class ConsultasFalsas:
    def __init__(self) -> None:
        self.criterios: CriteriosBusqueda | None = None
        self.fallar = False

    async def buscar(self, criterios: CriteriosBusqueda) -> PaginaServicios:
        if self.fallar:
            raise RuntimeError("PostGIS no responde")
        self.criterios = criterios
        return PaginaServicios(
            items=(SERVICIO,), pagina=criterios.pagina, tamano=criterios.tamano, total=1
        )

    async def detalle(self, servicio_id: UUID, ahora: datetime) -> ServicioDetalle | None:
        if servicio_id != SERVICIO_ID:
            return None
        return ServicioDetalle(
            resumen=SERVICIO,
            descripcion=TextoTraducido(es="Recorrido por fincas", en="Farm walk"),
            capacidad_aforo_diario=20,
            imagenes_urls=(),
            prestador=PrestadorPublico(
                id=uuid4(),
                razon_social="Café de la Sierra",
                telefono=None,
                politica_cancelacion=TextoTraducido(es="Gratis 24 h antes", en="Free 24 h before"),
            ),
            alertas=(ALERTA,),
            atributos=ATRIBUTOS,
        )

    async def activas(self) -> list[ZonaVista]:
        return [
            ZonaVista(uuid4(), TAYRONA.codigo, TAYRONA.nombre, Coordenada(11.3, -74.0)),
            ZonaVista(uuid4(), MINCA.codigo, MINCA.nombre, Coordenada(11.14, -74.11)),
        ]

    async def vigentes(
        self, ahora: datetime, zona: str | None = None, servicio_id: UUID | None = None
    ) -> list[AlertaVista]:
        return [ALERTA]


@pytest.fixture
def consultas() -> ConsultasFalsas:
    return ConsultasFalsas()


@pytest.fixture
def cliente(consultas: ConsultasFalsas) -> Iterator[TestClient]:
    app = create_app()
    for dependencia in (get_consulta_servicios, get_consulta_zonas, get_consulta_alertas):
        app.dependency_overrides[dependencia] = lambda: consultas
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestIdioma:
    def test_busqueda_en_espanol_por_defecto(self, cliente: TestClient) -> None:
        r = cliente.get("/api/catalog/buscar")
        assert r.status_code == 200 and r.headers["content-language"] == "es"
        item = r.json()["items"][0]
        assert (item["nombre"], item["categoria"], item["categoria_etiqueta"]) == (
            "Tour del café",
            "GASTRONOMIA",
            "Gastronomía",
        )
        assert item["tarifa_base"] == 85000.5  # número, no texto
        assert item["disponibilidad_confirmada"] is None  # sin fecha

    def test_misma_busqueda_en_ingles(self, cliente: TestClient) -> None:
        r = cliente.get("/api/catalog/buscar", headers={"Accept-Language": "en-US,en;q=0.9"})
        assert r.headers["content-language"] == "en"
        item = r.json()["items"][0]
        assert (item["nombre"], item["categoria_etiqueta"]) == ("Coffee tour", "Food & dining")

    def test_detalle_en_ingles_con_textos_sin_traducir(self, cliente: TestClient) -> None:
        r = cliente.get(f"/api/catalog/servicios/{SERVICIO_ID}", headers={"Accept-Language": "en"})
        cuerpo = r.json()
        assert cuerpo["descripcion"] == "Farm walk"
        assert cuerpo["prestador"]["politica_cancelacion"] == "Free 24 h before"
        assert cuerpo["regla_base_cancelacion"].startswith("Platform rule: you can cancel")
        alerta = cuerpo["alertas"][0]
        assert (alerta["nivel_etiqueta"], alerta["mensaje"]) == ("Critical", "Sendero cerrado")

    def test_zonas_ordenadas_por_nombre_en_el_idioma(self, cliente: TestClient) -> None:
        es = [z["nombre"] for z in cliente.get("/api/catalog/zonas").json()]
        en = [
            z["nombre"]
            for z in cliente.get("/api/catalog/zonas", headers={"Accept-Language": "en"}).json()
        ]
        assert es == ["Minca", "Parque Nacional Natural Tayrona"]
        assert en == ["Minca", "Tayrona National Natural Park"]


class TestFichaConAtributos:
    def test_resumen_con_tipo_y_unidad(self, cliente: TestClient) -> None:
        item = cliente.get("/api/catalog/buscar", headers={"Accept-Language": "en"}).json()[
            "items"
        ][0]
        assert (item["tipo"], item["tipo_etiqueta"]) == (
            "EXPERIENCIA_GASTRONOMICA",
            "Food experience",
        )
        assert (item["unidad_tarifa"], item["unidad_tarifa_etiqueta"]) == (
            "POR_PERSONA",
            "per person",
        )

    def test_atributos_en_el_idioma_pedido_con_etiquetas(self, cliente: TestClient) -> None:
        cuerpo = cliente.get(
            f"/api/catalog/servicios/{SERVICIO_ID}", headers={"Accept-Language": "en"}
        ).json()
        atributos = cuerpo["atributos"]
        assert atributos["experiencia"]["punto_encuentro"] == "Minca park"
        assert atributos["pagos"]["cajeros"]["referencia"] == "Minca park"
        assert atributos["pagos"]["medios_pago"] == ["EFECTIVO"]
        assert cuerpo["etiquetas"]["SIN_SENAL"] == "No signal"
        assert cuerpo["etiquetas"]["MEDIO"] == "Medium"

    def test_aviso_de_pagos_en_espanol(self, cliente: TestClient) -> None:
        aviso = cliente.get(f"/api/catalog/servicios/{SERVICIO_ID}").json()["aviso_pagos"]
        assert aviso["importante"] is True and aviso["recomendacion_dinero"] == "EFECTIVO"
        assert aviso["mensaje"] == (
            "Lleva efectivo: no hay señal de internet, solo se acepta efectivo y no hay "
            "cajeros cerca (el más cercano: Parque de Minca, a 8 km). El prestador ofrece "
            "crédito: si no tienes cómo pagar, le pagas después (plazo: 3 días). Es un acuerdo "
            "con el prestador; la plataforma no lo cobra ni lo garantiza."
        )

    def test_aviso_de_pagos_en_ingles(self, cliente: TestClient) -> None:
        aviso = cliente.get(
            f"/api/catalog/servicios/{SERVICIO_ID}", headers={"Accept-Language": "en"}
        ).json()["aviso_pagos"]
        assert aviso["mensaje"].startswith(
            "Bring cash: there is no internet signal, only cash is accepted and there are no "
            "ATMs nearby (nearest one: Minca park, 8 km away)."
        )


class TestParametros:
    def test_filtros_de_tipo_y_atributos(
        self, cliente: TestClient, consultas: ConsultasFalsas
    ) -> None:
        r = cliente.get(
            "/api/catalog/buscar",
            params={
                "tipo": "hostal,HOTEL",
                "unidad_tarifa": "POR_NOCHE",
                "idioma_atencion": "en",
                "accesible": "true",
                "mascotas": "false",
                "opcion_dietaria": "VEGANA",
                "nivel_fisico": "BAJO",
                "acepta_pago_digital": "true",
                "ofrece_credito": "true",
                "fecha": "2026-11-05",
                "personas": 3,
            },
        )
        assert r.status_code == 200
        c = consultas.criterios
        assert c is not None
        f = c.filtros
        assert (f.fecha.isoformat() if f.fecha else None, f.personas) == ("2026-11-05", 3)
        assert f.tipos == (TipoServicio.HOSTAL, TipoServicio.HOTEL)
        assert f.unidad_tarifa is UnidadTarifa.POR_NOCHE
        assert f.opcion_dietaria is OpcionDietaria.VEGANA
        assert f.filtro_atributos() == {
            "comunes": {"accesible": True, "mascotas": False, "idiomas_atencion": ["en"]},
            "gastronomia": {"opciones_dietarias": ["VEGANA"]},
            "experiencia": {"nivel_fisico": "BAJO"},
            "pagos": {"acepta_pago_digital": True, "credito": {"ofrece": True}},
        }

    def test_tipo_desconocido(self, cliente: TestClient) -> None:
        r = cliente.get("/api/catalog/buscar", params={"tipo": "HOSTAL,CASTILLO"})
        assert r.status_code == 400

    def test_filtros_llegan_validados(
        self, cliente: TestClient, consultas: ConsultasFalsas
    ) -> None:
        r = cliente.get(
            "/api/catalog/buscar",
            params={
                "texto": "playa tranquila",
                "categoria": "playa, cultura",
                "zona": "taganga",
                "precio_max": "200000",
                "lat": 11.27,
                "lon": -74.19,
                "radio_m": 2000,
                "orden": "distancia",
            },
        )
        assert r.status_code == 200
        c = consultas.criterios
        assert c is not None
        assert c.categorias == (Categoria.CULTURA, Categoria.PLAYA)
        assert c.cerca_de == Coordenada(lat=11.27, lon=-74.19)
        assert (c.radio_m, c.orden, c.precio_max) == (
            2000,
            OrdenBusqueda.DISTANCIA,
            Decimal("200000"),
        )

    def test_listar_catalogo_usa_una_categoria(
        self, cliente: TestClient, consultas: ConsultasFalsas
    ) -> None:
        cliente.get("/api/catalog/servicios", params={"categoria": "PLAYA", "tamano": 5})
        assert consultas.criterios is not None
        assert (
            consultas.criterios.categorias == (Categoria.PLAYA,) and consultas.criterios.tamano == 5
        )


class TestErrores:
    @pytest.mark.parametrize(
        ("params", "idioma", "mensaje"),
        [
            ({"lat": 11.2}, "es", "El campo «lon» es obligatorio."),
            ({"lat": 11.2}, "en", "The field 'lon' is required."),
            ({"orden": "distancia"}, "en", "The field 'orden' also requires: lat, lon."),
            (
                {"categoria": "PLAYA,MONTAÑA"},
                "es",
                "El campo «categoria» no tiene un formato válido.",
            ),
            ({"radio_m": 10}, "es", "El campo «radio_m» no tiene un formato válido."),
            ({"tamano": 51}, "en", "The field 'tamano' has an invalid format."),
        ],
    )
    def test_validacion_en_el_idioma_pedido(
        self, cliente: TestClient, params: dict, idioma: str, mensaje: str
    ) -> None:
        r = cliente.get("/api/catalog/buscar", params=params, headers={"Accept-Language": idioma})
        assert r.status_code == 400
        assert r.json()["error"] == "VALIDACION" and r.json()["message"] == mensaje
        assert r.headers["content-language"] == idioma

    def test_servicio_inexistente(self, cliente: TestClient) -> None:
        r = cliente.get(f"/api/catalog/servicios/{uuid4()}", headers={"Accept-Language": "en"})
        assert r.status_code == 404
        assert r.json()["error"] == "NO_ENCONTRADO"
        assert r.json()["message"].startswith("The requested resource")

    @pytest.mark.sin_contrato  # un 500 no es parte del contrato; aquí se provoca a propósito
    def test_error_inesperado_no_filtra_detalles(
        self, cliente: TestClient, consultas: ConsultasFalsas
    ) -> None:
        consultas.fallar = True
        r = cliente.get("/api/catalog/buscar", headers={"X-Correlation-ID": "abc-123"})
        assert r.status_code == 500
        assert r.json()["error"] == "ERROR_INTERNO" and "PostGIS" not in r.json()["message"]
        assert r.json()["correlation_id"] == "abc-123"
        assert r.headers["x-correlation-id"] == "abc-123"


class TestCorrelacion:
    def test_se_propaga_el_id_recibido(self, cliente: TestClient) -> None:
        r = cliente.get(f"/api/catalog/servicios/{uuid4()}", headers={"X-Correlation-ID": "corr-1"})
        assert r.headers["x-correlation-id"] == "corr-1"
        assert r.json()["correlation_id"] == "corr-1"

    @pytest.mark.parametrize("recibido", [None, "con espacios y ;", "x" * 101])
    def test_se_genera_uno_si_falta_o_es_invalido(
        self, cliente: TestClient, recibido: str | None
    ) -> None:
        cabeceras = {"X-Correlation-ID": recibido} if recibido else {}
        r = cliente.get("/api/catalog/zonas", headers=cabeceras)
        assert str(UUID(r.headers["x-correlation-id"])) == r.headers["x-correlation-id"]


def test_las_alertas_expiran_en_el_futuro() -> None:
    # Sanidad del doble usado arriba: evita que una prueba pase con datos imposibles.
    assert ALERTA.fecha_expiracion > datetime(2026, 10, 18, tzinfo=UTC) - timedelta(days=1)
