"""El mock-plataforma responde con las formas de los contratos de catalog, booking y review.

Si un contrato cambia, estas pruebas avisan que el mock (y quizá las tools) quedaron atrás.
"""

import pytest
from fastapi.testclient import TestClient

from mocks.app import app
from mocks.datos import SERVICIOS, TURISTA_CON_HISTORIAL
from tests.contratos import validar as _validar

TURISTA = {"X-Usuario-Id": str(TURISTA_CON_HISTORIAL), "X-Usuario-Rol": "Turista"}
SERVICIO = str(SERVICIOS[0]["id"])
SIN_RESENAS = str(SERVICIOS[-1]["id"])
INEXISTENTE = "00000000-0000-4000-8000-000000000000"

cliente = TestClient(app)


CASOS = [
    # (contrato, ruta del contrato, URL del mock, cabeceras, estado)
    ("catalog.yaml", "/buscar", "/api/catalog/buscar", {}, 200),
    (
        "catalog.yaml",
        "/buscar",
        "/api/catalog/buscar?texto=minca&categoria=CULTURA,NATURALEZA",
        {},
        200,
    ),
    ("catalog.yaml", "/buscar", "/api/catalog/buscar?fecha=2026-11-08&personas=2", {}, 200),
    ("catalog.yaml", "/buscar", "/api/catalog/buscar?personas=2", {}, 400),
    ("catalog.yaml", "/servicios/{servicio_id}", f"/api/catalog/servicios/{INEXISTENTE}", {}, 404),
    ("catalog.yaml", "/alertas", "/api/catalog/alertas", {"Accept-Language": "en"}, 200),
    ("catalog.yaml", "/alertas", f"/api/catalog/alertas?servicio_id={SERVICIO}", {}, 200),
    ("catalog.yaml", "/analitica/capacidad", "/api/catalog/analitica/capacidad", TURISTA, 200),
    (
        "catalog.yaml",
        "/analitica/capacidad",
        "/api/catalog/analitica/capacidad?zona=minca",
        {"X-Usuario-Id": str(TURISTA_CON_HISTORIAL), "X-Usuario-Rol": "Entidad"},
        200,
    ),
    ("catalog.yaml", "/analitica/capacidad", "/api/catalog/analitica/capacidad", {}, 401),
    (
        "catalog.yaml",
        "/analitica/capacidad",
        "/api/catalog/analitica/capacidad?zona=narnia",
        TURISTA,
        404,
    ),
    (
        "booking.yaml",
        "/disponibilidad",
        f"/api/bookings/disponibilidad?servicio_id={SERVICIO}&desde=2026-11-01&hasta=2026-11-10",
        {},
        200,
    ),
    (
        "booking.yaml",
        "/disponibilidad",
        f"/api/bookings/disponibilidad?servicio_id={SERVICIO}&desde=2026-11-01&hasta=2027-02-01",
        {},
        400,
    ),
    ("booking.yaml", "/mis-reservas", "/api/bookings/mis-reservas", TURISTA, 200),
    ("booking.yaml", "/mis-reservas", "/api/bookings/mis-reservas", {}, 401),
    (
        "review.yaml",
        "/servicios/{servicio_id}/resenas",
        f"/api/reviews/servicios/{SERVICIO}/resenas",
        {},
        200,
    ),
    (
        "review.yaml",
        "/servicios/{servicio_id}/resumen",
        f"/api/reviews/servicios/{SERVICIO}/resumen",
        {},
        200,
    ),
    (
        "review.yaml",
        "/servicios/{servicio_id}/resumen",
        f"/api/reviews/servicios/{SIN_RESENAS}/resumen",
        {},
        200,
    ),
]


@pytest.mark.parametrize(("archivo", "ruta", "url", "cabeceras", "estado"), CASOS)
def test_el_mock_cumple_el_contrato(archivo, ruta, url, cabeceras, estado):
    respuesta = cliente.get(url, headers=cabeceras)

    assert respuesta.status_code == estado
    _validar(archivo, ruta, estado, respuesta.json())


@pytest.mark.parametrize("servicio", SERVICIOS, ids=lambda s: s["nombre"])
def test_la_ficha_de_cada_servicio_cumple_el_contrato(servicio):
    respuesta = cliente.get(f"/api/catalog/servicios/{servicio['id']}")

    assert respuesta.status_code == 200
    _validar("catalog.yaml", "/servicios/{servicio_id}", 200, respuesta.json())


def test_la_calificacion_del_catalogo_coincide_con_la_de_review():
    for servicio in SERVICIOS:
        ficha = cliente.get(f"/api/catalog/servicios/{servicio['id']}").json()
        resumen = cliente.get(f"/api/reviews/servicios/{servicio['id']}/resumen").json()

        assert ficha["calificacion_promedio"] == resumen["promedio"]
        assert ficha["total_resenas"] == resumen["total"]
