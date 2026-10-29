"""Alertas oficiales (UC26) completas: HTTP → caso de uso → PostGIS y outbox reales."""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.main import create_app

pytestmark = pytest.mark.integration

ENTIDAD = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Entidad"}
MINCA = {"lat": 11.1426, "lon": -74.1178}  # dentro de la zona inicial `minca`


def en(dias: float) -> str:
    return (datetime.now(UTC) + timedelta(days=dias)).isoformat()


def alerta(**cambios: Any) -> dict[str, Any]:
    return {
        "nivel": "PREVENTIVA",
        "mensaje": {"es": "Sendero cerrado por lluvias", "en": "Trail closed due to rain"},
        "fecha_expiracion": en(2),
        "zona": "minca",
    } | cambios


def en_la_base(
    url: str, operacion: Callable[[async_sessionmaker[AsyncSession]], Awaitable[Any]]
) -> Any:
    async def correr() -> Any:
        engine = build_engine(url)
        try:
            return await operacion(build_session_factory(engine))
        finally:
            await engine.dispose()

    return asyncio.run(correr())


def auditorias(url: str, alerta_id: str) -> list[str]:
    async def leer(sesiones: async_sessionmaker[AsyncSession]) -> list[str]:
        async with sesiones() as session:
            filas = await session.scalars(
                text(
                    "SELECT sobre->'payload'->>'accion' FROM outbox"
                    " WHERE sobre->'payload'->'detalles'->>'alerta_id' = :id"
                    " ORDER BY (sobre->'payload'->'detalles'->>'version')::int"
                ),
                {"id": alerta_id},
            )
            return list(filas)

    return en_la_base(url, leer)


@pytest.fixture
def cliente(database_url: str, valkey_url: str, engine: object) -> Iterator[TestClient]:
    settings = get_settings().model_copy(
        update={
            "database_url": database_url,
            "valkey_url": valkey_url,
            "imagenes_url_publica": "http://imagenes.test/catalogo-imagenes",
            "s3_access_key": "prueba",
            "s3_secret_key": "prueba",
        }
    )
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def servicio(database_url: str, cliente: TestClient) -> dict[str, Any]:
    """Un servicio activo en Minca y las cabeceras de su prestador."""
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Minca Viva")

    async def guardar(sesiones: async_sessionmaker[AsyncSession]) -> None:
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.prestadores.guardar(perfil)
            await uow.confirmar()

    en_la_base(database_url, guardar)
    cabeceras = {"X-Usuario-Id": str(perfil.usuario_id), "X-Usuario-Rol": "Prestador"}
    r = cliente.post(
        "/api/catalog/servicios",
        json={
            "nombre": {"es": "Caminata a Pozo Azul"},
            "descripcion": {"es": "Sendero por el río"},
            "tipo": "SENDERISMO",
            "ubicacion": MINCA,
            "tarifa_base": 30000,
            "unidad_tarifa": "POR_PERSONA",
            "capacidad_aforo_diario": 20,
            "atributos": {"experiencia": {"duracion_minutos": 120, "nivel_fisico": "MEDIO"}},
        },
        headers=cabeceras,
    )
    assert r.status_code == 201, r.text
    return r.json() | {"cabeceras": cabeceras}


def publicar(cliente: TestClient, **cambios: Any) -> dict[str, Any]:
    r = cliente.post("/api/catalog/alertas", json=alerta(**cambios), headers=ENTIDAD)
    assert r.status_code == 201, r.text
    return r.json()


class TestPublicar:
    def test_alerta_de_zona_se_ve_en_lista_ficha_y_mapa(
        self, cliente: TestClient, servicio: dict, database_url: str
    ) -> None:
        r = cliente.post("/api/catalog/alertas", json=alerta(), headers=ENTIDAD)
        assert r.status_code == 201 and r.headers["etag"] == '"1"'
        creada = r.json()
        assert (creada["zona"], creada["estado"], creada["version"]) == ("minca", "VIGENTE", 1)
        assert creada["entidad_usuario_id"] == ENTIDAD["X-Usuario-Id"]

        publicas = cliente.get(
            "/api/catalog/alertas", params={"zona": "minca"}, headers={"Accept-Language": "en"}
        ).json()
        assert [(a["id"], a["mensaje"], a["nivel_etiqueta"]) for a in publicas] == [
            (creada["id"], "Trail closed due to rain", "Advisory")
        ]
        # La alerta de la zona afecta al servicio que está en ella.
        ficha = cliente.get(f"/api/catalog/servicios/{servicio['id']}").json()
        assert [a["id"] for a in ficha["alertas"]] == [creada["id"]]
        mapa = cliente.get("/api/catalog/mapa/alertas").json()
        assert creada["id"] in [f["properties"]["id"] for f in mapa["features"]]
        assert auditorias(database_url, creada["id"]) == ["ALERTA_PUBLICADA"]

    def test_alerta_de_servicio(self, cliente: TestClient, servicio: dict) -> None:
        creada = publicar(cliente, zona=None, servicio_id=servicio["id"], nivel="CRITICA")
        assert (creada["servicio_id"], creada["zona"]) == (servicio["id"], None)
        ficha = cliente.get(f"/api/catalog/servicios/{servicio['id']}").json()
        assert ficha["alertas"][0]["nivel"] == "CRITICA"

    @pytest.mark.parametrize(
        ("cambios", "estado"),
        [
            ({"servicio_id": str(uuid4())}, 400),  # servicio y zona a la vez
            ({"zona": None}, 400),  # ninguno
            ({"fecha_expiracion": en(-1)}, 400),
            ({"fecha_expiracion": en(400)}, 400),  # más de un año
            ({"fecha_expiracion": "2026-12-01T10:00:00"}, 400),  # sin zona horaria
            ({"zona": "no-existe"}, 404),
            ({"zona": None, "servicio_id": str(uuid4())}, 404),
        ],
        ids=[
            "dos_destinos",
            "sin_destino",
            "pasada",
            "mas_de_un_anio",
            "sin_zona_horaria",
            "zona_inexistente",
            "servicio_inexistente",
        ],
    )
    def test_reglas(self, cliente: TestClient, cambios: dict, estado: int) -> None:
        r = cliente.post("/api/catalog/alertas", json=alerta(**cambios), headers=ENTIDAD)
        assert r.status_code == estado, r.text

    def test_mensaje_del_plazo_maximo(self, cliente: TestClient) -> None:
        r = cliente.post(
            "/api/catalog/alertas", json=alerta(fecha_expiracion=en(400)), headers=ENTIDAD
        )
        assert (
            r.json()["message"]
            == "La fecha de «fecha_expiracion» no puede estar a más de 365 días."
        )

    def test_servicio_inactivo_es_404(self, cliente: TestClient, servicio: dict) -> None:
        r = cliente.post(
            f"/api/catalog/servicios/{servicio['id']}/desactivar",
            headers=servicio["cabeceras"] | {"If-Match": '"1"'},
        )
        assert r.status_code == 200
        r = cliente.post(
            "/api/catalog/alertas",
            json=alerta(zona=None, servicio_id=servicio["id"]),
            headers=ENTIDAD,
        )
        assert r.status_code == 404

    def test_prestador_no_puede(self, cliente: TestClient, servicio: dict) -> None:
        r = cliente.post("/api/catalog/alertas", json=alerta(), headers=servicio["cabeceras"])
        assert r.status_code == 403 and r.json()["error"] == "ROL_NO_PERMITIDO"


class TestEditarYRetirar:
    def test_extender_la_vigencia(self, cliente: TestClient, database_url: str) -> None:
        creada = publicar(cliente)
        ruta = f"/api/catalog/alertas/{creada['id']}"
        cambio = {
            "nivel": "CRITICA",
            "mensaje": {"es": "Sendero cerrado una semana más"},
            "fecha_expiracion": en(9),
        }
        assert cliente.put(ruta, json=cambio, headers=ENTIDAD).status_code == 428
        r = cliente.put(ruta, json=cambio, headers=ENTIDAD | {"If-Match": '"1"'})
        assert r.status_code == 200 and r.headers["etag"] == '"2"'
        assert (r.json()["nivel"], r.json()["mensaje"]) == (
            "CRITICA",
            {"es": "Sendero cerrado una semana más", "en": None},  # sin traducción
        )
        vieja = cliente.put(ruta, json=cambio, headers=ENTIDAD | {"If-Match": '"1"'})
        assert vieja.status_code == 409 and vieja.json()["error"] == "VERSION_DISTINTA"
        assert auditorias(database_url, creada["id"]) == ["ALERTA_PUBLICADA", "ALERTA_EDITADA"]

    def test_retirar_es_definitivo_y_repetir_no_audita(
        self, cliente: TestClient, database_url: str
    ) -> None:
        creada = publicar(cliente)
        ruta = f"/api/catalog/alertas/{creada['id']}"
        r = cliente.post(f"{ruta}/desactivar", headers=ENTIDAD)
        assert r.status_code == 200 and r.json()["estado"] == "RETIRADA"
        assert cliente.get("/api/catalog/alertas").json() == []
        assert cliente.post(f"{ruta}/desactivar", headers=ENTIDAD).status_code == 200
        assert auditorias(database_url, creada["id"]) == ["ALERTA_PUBLICADA", "ALERTA_RETIRADA"]

        editar = cliente.put(
            ruta,
            json={"nivel": "INFORMATIVA", "mensaje": {"es": "x"}, "fecha_expiracion": en(3)},
            headers=ENTIDAD | {"If-Match": '"2"'},
        )
        assert editar.status_code == 409 and editar.json()["error"] == "ALERTA_RETIRADA"

    def test_inexistente_es_404(self, cliente: TestClient) -> None:
        r = cliente.post(f"/api/catalog/alertas/{uuid4()}/desactivar", headers=ENTIDAD)
        assert r.status_code == 404


class TestPanelYZonas:
    def test_panel_por_estado(self, cliente: TestClient) -> None:
        vigente = publicar(cliente)
        retirada = publicar(cliente, nivel="INFORMATIVA")
        cliente.post(f"/api/catalog/alertas/{retirada['id']}/desactivar", headers=ENTIDAD)

        todas = cliente.get("/api/catalog/entidad/alertas", headers=ENTIDAD).json()
        assert todas["total"] == 2
        assert [a["id"] for a in todas["items"]] == [
            retirada["id"],
            vigente["id"],
        ]  # recientes primero
        solo = cliente.get(
            "/api/catalog/entidad/alertas",
            params={"estado": "RETIRADA"},
            headers=ENTIDAD | {"Accept-Language": "en"},
        ).json()
        assert [(a["id"], a["estado_etiqueta"]) for a in solo["items"]] == [
            (retirada["id"], "Withdrawn")
        ]
        turista = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Turista"}
        assert cliente.get("/api/catalog/entidad/alertas", headers=turista).status_code == 403

    def test_una_zona_con_alerta_vigente_no_se_desactiva(self, cliente: TestClient) -> None:
        anillo = [
            [-74.05, 11.05],
            [-74.04, 11.05],
            [-74.04, 11.06],
            [-74.05, 11.06],
            [-74.05, 11.05],
        ]
        zona = cliente.post(
            "/api/catalog/zonas",
            json={
                "codigo": "prueba-alerta",
                "nombre": {"es": "Prueba"},
                "poligono": {"type": "Polygon", "coordinates": [anillo]},
            },
            headers=ENTIDAD,
        ).json()
        creada = publicar(cliente, zona="prueba-alerta")
        ruta = f"/api/catalog/zonas/{zona['id']}/desactivar"
        r = cliente.post(ruta, headers=ENTIDAD | {"If-Match": '"1"'})
        assert r.status_code == 409 and r.json()["error"] == "ZONA_EN_USO"

        cliente.post(f"/api/catalog/alertas/{creada['id']}/desactivar", headers=ENTIDAD)
        assert cliente.post(ruta, headers=ENTIDAD | {"If-Match": '"1"'}).status_code == 200
