import json
from uuid import uuid4

import httpx
import pytest

from mocks.app import app as mock_plataforma
from mocks.datos import SERVICIOS, TURISTA_CON_HISTORIAL
from src.application.ports.herramientas import ContextoTurista
from src.infrastructure.tools.herramientas_plataforma import HerramientasPlataforma

CONTEXTO = ContextoTurista(turista_id=TURISTA_CON_HISTORIAL)
BUCEO = SERVICIOS[0]["id"]
CAFE_MINCA = SERVICIOS[1]["id"]
NOMBRES = {
    "buscar_servicios",
    "detalle_servicio",
    "consultar_disponibilidad",
    "historial_turista",
    "resenas_servicio",
    "presion_capacidad_carga",
    "alertas_oficiales",
}


def _herramientas(transporte: httpx.AsyncBaseTransport) -> HerramientasPlataforma:
    cliente = httpx.AsyncClient(transport=transporte)
    return HerramientasPlataforma(
        cliente,
        "http://plataforma/api/catalog",
        "http://plataforma/api/bookings",
        "http://plataforma/api/reviews",
    )


@pytest.fixture
def herramientas():
    """Tools contra el mock-plataforma en proceso (sin red ni contenedores)."""
    return _herramientas(httpx.ASGITransport(app=mock_plataforma))


class Grabadora:
    """Transporte que guarda las peticiones y responde lo que se le indique."""

    def __init__(self, respuesta: httpx.Response | Exception | None = None) -> None:
        self.peticiones: list[httpx.Request] = []
        self._respuesta = respuesta or httpx.Response(200, json={})

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        if isinstance(self._respuesta, Exception):
            raise self._respuesta
        return self._respuesta


def _con(grabadora: Grabadora) -> HerramientasPlataforma:
    return _herramientas(httpx.MockTransport(grabadora))


# ---------- declaraciones ----------


def test_declara_las_7_tools():
    declaraciones = _con(Grabadora()).declaraciones()

    assert {d.nombre for d in declaraciones} == NOMBRES
    assert all(d.descripcion for d in declaraciones)


def test_los_parametros_son_json_schema_plano():
    for declaracion in _con(Grabadora()).declaraciones():
        texto = json.dumps(declaracion.parametros)

        assert declaracion.parametros["type"] == "object"
        assert '"title"' not in texto
        assert "$ref" not in texto and "$defs" not in texto
        assert '{"type": "null"}' not in texto


def test_ninguna_tool_permite_elegir_el_turista():
    for declaracion in _con(Grabadora()).declaraciones():
        assert "turista_id" not in declaracion.parametros.get("properties", {})

    historial = next(
        d for d in _con(Grabadora()).declaraciones() if d.nombre == "historial_turista"
    )
    assert historial.parametros.get("properties", {}) == {}


# ---------- cada tool contra el mock ----------


async def test_buscar_servicios(herramientas):
    resultado = await herramientas.ejecutar("buscar_servicios", {"zona": "minca"}, CONTEXTO)

    assert resultado.ok
    nombres = {s["nombre"] for s in resultado.datos["servicios"]}
    assert nombres == {"Tour de café en Minca", "Avistamiento de aves en Minca"}
    assert resultado.servicios_vistos == {SERVICIOS[1]["id"], SERVICIOS[2]["id"]}
    # Recortado: sin coordenadas ni imágenes.
    assert "ubicacion" not in resultado.datos["servicios"][0]
    assert "imagen_principal" not in resultado.datos["servicios"][0]


async def test_buscar_servicios_con_texto_categorias_y_fecha(herramientas):
    resultado = await herramientas.ejecutar(
        "buscar_servicios",
        {"texto": "cafe", "categorias": ["CULTURA"], "fecha": "2026-11-08", "personas": 2},
        CONTEXTO,
    )

    assert resultado.ok
    [servicio] = resultado.datos["servicios"]
    assert servicio["nombre"] == "Tour de café en Minca"
    assert servicio["cupos_disponibles"] >= 2


async def test_detalle_servicio(herramientas):
    resultado = await herramientas.ejecutar(
        "detalle_servicio", {"servicio_id": str(CAFE_MINCA)}, CONTEXTO
    )

    assert resultado.ok
    assert resultado.datos["prestador"] == "Finca La Victoria"
    assert resultado.datos["aviso_pagos"].startswith("Lleva efectivo")
    assert resultado.datos["alertas"][0]["nivel"] == "INFORMATIVA"
    assert resultado.servicios_vistos == {CAFE_MINCA}
    assert "telefono" not in json.dumps(resultado.datos)


async def test_detalle_de_un_servicio_inexistente(herramientas):
    resultado = await herramientas.ejecutar(
        "detalle_servicio", {"servicio_id": str(uuid4())}, CONTEXTO
    )

    assert resultado.error == "NO_ENCONTRADO"
    assert resultado.servicios_vistos == frozenset()


async def test_consultar_disponibilidad(herramientas):
    resultado = await herramientas.ejecutar(
        "consultar_disponibilidad",
        {"servicio_id": str(BUCEO), "desde": "2026-11-01", "hasta": "2026-11-07"},
        CONTEXTO,
    )

    assert resultado.ok
    assert [d["fecha"] for d in resultado.datos["dias"]][0] == "2026-11-01"
    assert len(resultado.datos["dias"]) == 7
    # Consultar disponibilidad no convierte un id en recomendable.
    assert resultado.servicios_vistos == frozenset()


async def test_consultar_disponibilidad_de_un_solo_dia(herramientas):
    resultado = await herramientas.ejecutar(
        "consultar_disponibilidad", {"servicio_id": str(BUCEO), "desde": "2026-11-01"}, CONTEXTO
    )

    assert len(resultado.datos["dias"]) == 1


async def test_historial_turista(herramientas):
    resultado = await herramientas.ejecutar("historial_turista", {}, CONTEXTO)

    assert resultado.ok
    assert [r["estado"] for r in resultado.datos["reservas"]] == ["CONFIRMADA", "FINALIZADA"]
    assert resultado.servicios_vistos == {BUCEO, CAFE_MINCA}
    texto = json.dumps(resultado.datos)
    assert str(TURISTA_CON_HISTORIAL) not in texto
    assert "prestador_id" not in texto


async def test_historial_de_otro_turista_esta_vacio(herramientas):
    resultado = await herramientas.ejecutar(
        "historial_turista", {}, ContextoTurista(turista_id=uuid4())
    )

    assert resultado.datos == {"reservas": []}


async def test_resenas_servicio(herramientas):
    resultado = await herramientas.ejecutar(
        "resenas_servicio", {"servicio_id": str(BUCEO)}, CONTEXTO
    )

    assert resultado.ok
    assert resultado.datos["total"] == 3
    assert resultado.datos["promedio"] == pytest.approx(4.67)
    assert len(resultado.datos["recientes"]) == 3
    assert "autor" not in json.dumps(resultado.datos)


async def test_presion_capacidad_carga(herramientas):
    resultado = await herramientas.ejecutar("presion_capacidad_carga", {}, CONTEXTO)

    assert resultado.ok
    niveles = {z["zona_codigo"]: z["nivel"] for z in resultado.datos["zonas"]}
    assert niveles["tayrona"] == "ALTO"
    assert niveles["minca"] == "BAJO"
    # Para el rol Turista no viajan cifras.
    assert "indice" not in json.dumps(resultado.datos)


async def test_alertas_oficiales(herramientas):
    resultado = await herramientas.ejecutar("alertas_oficiales", {"zona": "tayrona"}, CONTEXTO)

    assert resultado.ok
    [alerta] = resultado.datos["alertas"]
    assert alerta["nivel"] == "CRITICA"
    assert alerta["zona"] == "Parque Tayrona"


async def test_las_respuestas_salen_en_el_idioma_del_turista(herramientas):
    resultado = await herramientas.ejecutar(
        "buscar_servicios", {"zona": "palomino"}, ContextoTurista(uuid4(), idioma="en")
    )

    assert {s["unidad_tarifa"] for s in resultado.datos["servicios"]} == {
        "per person",
        "per night",
    }


# ---------- identidad y cabeceras ----------


async def test_historial_usa_el_turista_del_contexto_aunque_el_modelo_mande_otro():
    grabadora = Grabadora(httpx.Response(200, json={"items": []}))
    otro = str(uuid4())

    await _con(grabadora).ejecutar("historial_turista", {"turista_id": otro}, CONTEXTO)

    [peticion] = grabadora.peticiones
    assert peticion.headers["X-Usuario-Id"] == str(TURISTA_CON_HISTORIAL)
    assert peticion.headers["X-Usuario-Rol"] == "Turista"
    assert otro not in str(peticion.url)


async def test_capacidad_reenvia_la_identidad_y_el_idioma():
    grabadora = Grabadora(httpx.Response(200, json=[]))

    await _con(grabadora).ejecutar(
        "presion_capacidad_carga", {"zona": "minca"}, ContextoTurista(uuid4(), idioma="en")
    )

    [peticion] = grabadora.peticiones
    assert peticion.url.path == "/api/catalog/analitica/capacidad"
    assert peticion.url.params["zona"] == "minca"
    assert peticion.headers["X-Usuario-Rol"] == "Turista"
    assert peticion.headers["Accept-Language"] == "en"


async def test_las_tools_publicas_no_envian_la_identidad():
    grabadora = Grabadora(httpx.Response(200, json=[]))

    await _con(grabadora).ejecutar("alertas_oficiales", {}, CONTEXTO)

    assert "X-Usuario-Id" not in grabadora.peticiones[0].headers


async def test_buscar_traduce_los_argumentos_a_los_parametros_del_contrato():
    grabadora = Grabadora(httpx.Response(200, json={"items": [], "total": 0}))

    await _con(grabadora).ejecutar(
        "buscar_servicios",
        {"categorias": ["PLAYA", "AVENTURA"], "lat": 11.24, "lon": -74.2, "texto": None},
        CONTEXTO,
    )

    [busqueda] = [p for p in grabadora.peticiones if p.url.path.endswith("/buscar")]
    params = busqueda.url.params
    assert params["categoria"] == "PLAYA,AVENTURA"
    assert params["lat"] == "11.24"
    assert params["tamano"] == "8"
    assert "texto" not in params


async def test_solo_hace_peticiones_get():
    grabadora = Grabadora(httpx.Response(200, json={"items": [], "total": 0}))
    herramientas = _con(grabadora)

    await herramientas.ejecutar("buscar_servicios", {}, CONTEXTO)
    await herramientas.ejecutar("historial_turista", {}, CONTEXTO)

    assert {p.method for p in grabadora.peticiones} == {"GET"}


# ---------- argumentos inválidos (no llegan a la plataforma) ----------


@pytest.mark.parametrize(
    ("nombre", "argumentos"),
    [
        ("buscar_servicios", {"zona": "Zona Rara!"}),
        ("buscar_servicios", {"personas": 3}),
        ("buscar_servicios", {"lat": 11.2}),
        ("buscar_servicios", {"categorias": ["CASINO"]}),
        ("buscar_servicios", {"texto": "x" * 201}),
        ("detalle_servicio", {}),
        ("detalle_servicio", {"servicio_id": "no-es-un-uuid"}),
        (
            "consultar_disponibilidad",
            {"servicio_id": str(BUCEO), "desde": "2026-11-10", "hasta": "2026-11-01"},
        ),
        (
            "consultar_disponibilidad",
            {"servicio_id": str(BUCEO), "desde": "2026-11-01", "hasta": "2027-01-15"},
        ),
    ],
)
async def test_argumentos_invalidos(nombre, argumentos):
    grabadora = Grabadora()

    resultado = await _con(grabadora).ejecutar(nombre, argumentos, CONTEXTO)

    assert resultado.error == "ARGUMENTOS_INVALIDOS"
    assert resultado.datos["mensaje"]
    assert grabadora.peticiones == []


async def test_argumentos_que_no_son_un_objeto():
    resultado = await _con(Grabadora()).ejecutar("buscar_servicios", ["minca"], CONTEXTO)

    assert resultado.error == "ARGUMENTOS_INVALIDOS"


async def test_tool_inexistente():
    grabadora = Grabadora()

    resultado = await _con(grabadora).ejecutar("crear_reserva", {}, CONTEXTO)

    assert resultado.error == "HERRAMIENTA_DESCONOCIDA"
    assert "buscar_servicios" in resultado.datos["mensaje"]
    assert grabadora.peticiones == []


# ---------- fallas de la plataforma (error controlado, nunca una excepción) ----------


@pytest.mark.parametrize(
    ("respuesta", "codigo"),
    [
        (httpx.ConnectError("conexión rechazada"), "SERVICIO_NO_DISPONIBLE"),
        (httpx.ReadTimeout("sin respuesta"), "TIEMPO_AGOTADO"),
        (httpx.ConnectTimeout("no se pudo conectar"), "SERVICIO_NO_DISPONIBLE"),
        (httpx.Response(500, json={"error": "INTERNO"}), "SERVICIO_NO_DISPONIBLE"),
        (httpx.Response(503, text="no disponible"), "SERVICIO_NO_DISPONIBLE"),
        (httpx.Response(200, text="<html>no es json</html>"), "RESPUESTA_INESPERADA"),
        (httpx.Response(200, json={"otra": "forma"}), "RESPUESTA_INESPERADA"),
        (httpx.Response(200, json={"items": [{"id": "x"}], "total": 1}), "RESPUESTA_INESPERADA"),
        (httpx.Response(404, json={"error": "NO_ENCONTRADO"}), "NO_ENCONTRADO"),
    ],
)
async def test_fallas_de_la_plataforma(respuesta, codigo):
    resultado = await _con(Grabadora(respuesta)).ejecutar(
        "buscar_servicios", {"zona": "minca"}, CONTEXTO
    )

    assert resultado.error == codigo
    assert not resultado.ok
    assert resultado.servicios_vistos == frozenset()


async def test_una_solicitud_rechazada_trae_el_motivo_de_la_plataforma():
    rechazo = httpx.Response(
        400, json={"error": "VALIDACION", "message": "fecha fuera de rango", "correlation_id": "x"}
    )

    resultado = await _con(Grabadora(rechazo)).ejecutar("alertas_oficiales", {}, CONTEXTO)

    assert resultado.error == "SOLICITUD_RECHAZADA"
    assert resultado.datos["mensaje"] == "fecha fuera de rango"


async def test_una_solicitud_rechazada_sin_cuerpo_tiene_un_mensaje_generico():
    resultado = await _con(Grabadora(httpx.Response(400, text="bad"))).ejecutar(
        "alertas_oficiales", {}, CONTEXTO
    )

    assert resultado.error == "SOLICITUD_RECHAZADA"
    assert resultado.datos["mensaje"]


async def test_resenas_falla_si_falla_cualquiera_de_sus_dos_consultas():
    def manejador(peticion: httpx.Request) -> httpx.Response:
        if peticion.url.path.endswith("/resumen"):
            return httpx.Response(500)
        return httpx.Response(200, json={"items": [], "pagina": 1, "tamano": 5, "total": 0})

    resultado = await _herramientas(httpx.MockTransport(manejador)).ejecutar(
        "resenas_servicio", {"servicio_id": str(BUCEO)}, CONTEXTO
    )

    assert resultado.error == "SERVICIO_NO_DISPONIBLE"


# ---------- zonas: el modelo no conoce los códigos de antemano ----------


@pytest.mark.parametrize(
    ("escrita", "codigo"),
    [("Minca", "minca"), (" minca ", "minca"), ("Centro Histórico", "centro-historico")],
)
async def test_la_zona_se_normaliza_antes_de_consultar(escrita, codigo):
    grabadora = Grabadora(httpx.Response(200, json=[]))

    resultado = await _con(grabadora).ejecutar("alertas_oficiales", {"zona": escrita}, CONTEXTO)

    assert resultado.ok
    assert grabadora.peticiones[0].url.params["zona"] == codigo


async def test_una_zona_imposible_es_un_error_que_el_modelo_puede_corregir():
    grabadora = Grabadora()

    resultado = await _con(grabadora).ejecutar("presion_capacidad_carga", {"zona": "¿?"}, CONTEXTO)

    assert resultado.error == "ARGUMENTOS_INVALIDOS"
    assert grabadora.peticiones == []


def test_el_esquema_que_ve_el_proveedor_no_lleva_pattern():
    # Groq valida con el esquema y corta la petición si no se cumple (tool_use_failed).
    for declaracion in _con(Grabadora()).declaraciones():
        assert '"pattern"' not in json.dumps(declaracion.parametros), declaracion.nombre


async def test_los_resultados_traen_el_codigo_de_zona(herramientas):
    busqueda = await herramientas.ejecutar("buscar_servicios", {"zona": "minca"}, CONTEXTO)
    alertas = await herramientas.ejecutar("alertas_oficiales", {}, CONTEXTO)
    capacidad = await herramientas.ejecutar("presion_capacidad_carga", {}, CONTEXTO)

    assert {s["zona_codigo"] for s in busqueda.datos["servicios"]} == {"minca"}
    assert {a["zona_codigo"] for a in alertas.datos["alertas"]} == {"tayrona", "minca"}
    assert "tayrona" in {z["zona_codigo"] for z in capacidad.datos["zonas"]}


# ---------- la búsqueda trae capacidad y alertas (menos vueltas del modelo) ----------


async def test_la_busqueda_trae_capacidad_y_alertas_de_cada_servicio(herramientas):
    resultado = await herramientas.ejecutar(
        "buscar_servicios", {"categorias": ["NATURALEZA"]}, CONTEXTO
    )

    por_nombre = {s["nombre"]: s for s in resultado.datos["servicios"]}
    aves = por_nombre["Avistamiento de aves en Minca"]
    tayrona = por_nombre["Entrada al Parque Tayrona"]
    assert aves["nivel_capacidad_zona"] == "BAJO"
    assert [a["nivel"] for a in aves["alertas"]] == ["INFORMATIVA"]
    assert tayrona["nivel_capacidad_zona"] == "ALTO"
    assert [a["nivel"] for a in tayrona["alertas"]] == ["CRITICA"]


async def test_si_la_capacidad_o_las_alertas_fallan_la_busqueda_sale_igual():
    async def manejador(peticion: httpx.Request) -> httpx.Response:
        if peticion.url.path.endswith("/buscar"):
            return await httpx.ASGITransport(app=mock_plataforma).handle_async_request(peticion)
        return httpx.Response(503)

    resultado = await _herramientas(httpx.MockTransport(manejador)).ejecutar(
        "buscar_servicios", {"zona": "minca"}, CONTEXTO
    )

    assert resultado.ok
    servicio = resultado.datos["servicios"][0]
    assert "nivel_capacidad_zona" not in servicio
    assert "alertas" not in servicio


async def test_la_capacidad_de_la_busqueda_se_pide_con_la_identidad_del_turista():
    grabadora = Grabadora(httpx.Response(200, json={"items": [], "total": 0}))

    await _con(grabadora).ejecutar("buscar_servicios", {"fecha": "2026-11-20"}, CONTEXTO)

    [capacidad] = [p for p in grabadora.peticiones if p.url.path.endswith("/capacidad")]
    assert capacidad.headers["X-Usuario-Id"] == str(TURISTA_CON_HISTORIAL)
    assert capacidad.url.params["fecha"] == "2026-11-20"
