"""Administración de zonas completa: HTTP → caso de uso → PostGIS, outbox y Valkey reales."""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.domain.entities.alerta_oficial import AlertaOficial
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.catalogos import NivelAlerta
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.main import create_app

pytestmark = pytest.mark.integration

BASE_IMAGENES = "http://imagenes.test/catalogo-imagenes"
# Dentro de la zona inicial `centro-historico` (-74.2160, 11.2330, -74.1960, 11.2500).
CENTRO = {"lat": 11.2420, "lon": -74.2110}
ENTIDAD = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Entidad"}


def caja(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict:
    anillo = [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]
    return {"type": "Polygon", "coordinates": [anillo]}


# Más pequeña que `centro-historico` y cubre CENTRO: gana por menor área.
ALREDEDOR_DEL_CENTRO = caja(-74.2150, 11.2380, -74.2050, 11.2460)
LEJOS = caja(-74.0500, 11.0500, -74.0400, 11.0600)


def zona(codigo: str = "prueba-muelle", poligono: dict = ALREDEDOR_DEL_CENTRO) -> dict:
    return {"codigo": codigo, "nombre": {"es": "Muelle", "en": "Pier"}, "poligono": poligono}


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


def auditorias(url: str, zona_id: str) -> list[dict]:
    async def leer(sesiones: async_sessionmaker[AsyncSession]) -> list[dict]:
        async with sesiones() as session:
            filas = await session.scalars(
                text(
                    "SELECT sobre FROM outbox WHERE event_type = 'auditoria.registrada' "
                    "AND sobre->'payload'->'detalles'->>'zona_id' = :id "
                    "ORDER BY (sobre->'payload'->'detalles'->>'version')::int"
                ),
                {"id": zona_id},
            )
            return list(filas)

    return en_la_base(url, leer)


def alerta_en(url: str, zona_id: str) -> None:
    ahora = datetime.now(UTC)
    alerta = AlertaOficial.publicar(
        nivel=NivelAlerta.PREVENTIVA,
        mensaje=TextoTraducido(es="Marea alta"),
        entidad_usuario_id=uuid4(),
        fecha_expiracion=ahora + timedelta(days=1),
        ahora=ahora,
        zona_id=UUID(zona_id),
    )

    async def guardar(sesiones: async_sessionmaker[AsyncSession]) -> None:
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.alertas.guardar(alerta)
            await uow.confirmar()

    en_la_base(url, guardar)


@pytest.fixture
def cliente(database_url: str, valkey_url: str, engine: object) -> Iterator[TestClient]:
    # `engine` limpia las tablas y las zonas `prueba-*` al terminar.
    settings = get_settings().model_copy(
        update={
            "database_url": database_url,
            "valkey_url": valkey_url,
            "imagenes_url_publica": BASE_IMAGENES,
            "s3_access_key": "prueba",
            "s3_secret_key": "prueba",
        }
    )
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def servicio_id(database_url: str, cliente: TestClient) -> str:
    """Un servicio en CENTRO, registrado por un prestador aprobado."""
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Turismo Sierra")

    async def guardar(sesiones: async_sessionmaker[AsyncSession]) -> None:
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.prestadores.guardar(perfil)
            await uow.confirmar()

    en_la_base(database_url, guardar)
    r = cliente.post(
        "/api/catalog/servicios",
        json={
            "nombre": {"es": "Paseo en lancha"},
            "descripcion": {"es": "Recorrido por la bahía"},
            "tipo": "TRANSPORTE_MARITIMO",
            "unidad_tarifa": "POR_PERSONA",
            "atributos": {
                "transporte": {
                    "origen": {"es": "Taganga"},
                    "destino": {"es": "Playa Cristal"},
                    "duracion_minutos": 40,
                    "capacidad_vehiculo": 12,
                }
            },
            "ubicacion": CENTRO,
            "tarifa_base": 60000,
            "capacidad_aforo_diario": 12,
        },
        headers={"X-Usuario-Id": str(perfil.usuario_id), "X-Usuario-Rol": "Prestador"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def zona_del_servicio(cliente: TestClient, servicio_id: str) -> str | None:
    zona = cliente.get(f"/api/catalog/servicios/{servicio_id}").json()["zona"]
    return zona["codigo"] if zona else None


def crear(cliente: TestClient, **cambios: Any) -> dict:
    r = cliente.post("/api/catalog/zonas", json=zona(**cambios), headers=ENTIDAD)
    assert r.status_code == 201, r.text
    return r.json()


class TestCrear:
    def test_crea_reasigna_servicios_audita_e_invalida_cache(
        self, cliente: TestClient, servicio_id: str, database_url: str
    ) -> None:
        assert zona_del_servicio(cliente, servicio_id) == "centro-historico"
        busqueda = cliente.get("/api/catalog/buscar").json()  # queda en caché
        assert busqueda["items"][0]["zona"]["codigo"] == "centro-historico"

        r = cliente.post(
            "/api/catalog/zonas",
            json=zona(),
            headers=ENTIDAD | {"X-Correlation-ID": "corr-zona"},
        )
        assert r.status_code == 201 and r.headers["etag"] == '"1"'
        creada = r.json()
        assert creada["codigo"] == "prueba-muelle" and creada["activa"] is True
        assert creada["nombre"] == {"es": "Muelle", "en": "Pier"}
        assert creada["poligono"]["type"] == "MultiPolygon"

        assert zona_del_servicio(cliente, servicio_id) == "prueba-muelle"
        busqueda = cliente.get("/api/catalog/buscar").json()
        assert busqueda["items"][0]["zona"]["codigo"] == "prueba-muelle"  # caché invalidada
        codigos = [z["codigo"] for z in cliente.get("/api/catalog/zonas").json()]
        assert "prueba-muelle" in codigos

        [evento] = auditorias(database_url, creada["id"])
        assert evento["correlation_id"] == "corr-zona"
        assert evento["payload"] == {
            "usuario_id": ENTIDAD["X-Usuario-Id"],
            "accion": "ZONA_CREADA",
            "resultado": "EXITO",
            "detalles": {"zona_id": creada["id"], "codigo": "prueba-muelle", "version": 1},
        }

    def test_codigo_repetido(self, cliente: TestClient) -> None:
        crear(cliente)
        r = cliente.post("/api/catalog/zonas", json=zona(poligono=LEJOS), headers=ENTIDAD)
        assert r.status_code == 409 and r.json()["error"] == "CODIGO_EXISTENTE"

    def test_poligono_que_se_cruza(self, cliente: TestClient) -> None:
        corbatin = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-74.05, 11.05],
                    [-74.04, 11.06],
                    [-74.04, 11.05],
                    [-74.05, 11.06],
                    [-74.05, 11.05],
                ]
            ],
        }
        r = cliente.post(
            "/api/catalog/zonas",
            json=zona(poligono=corbatin),
            headers=ENTIDAD | {"Accept-Language": "en"},
        )
        assert r.status_code == 400 and r.json()["error"] == "VALIDACION"
        assert r.json()["message"].startswith("The polygon is not valid")

    def test_codigo_con_formato_invalido(self, cliente: TestClient) -> None:
        r = cliente.post("/api/catalog/zonas", json=zona(codigo="Muelle 1"), headers=ENTIDAD)
        assert r.status_code == 400 and r.json()["error"] == "VALIDACION"

    @pytest.mark.parametrize("rol", ["Turista", "Prestador"])
    def test_otros_roles_403_y_se_audita(
        self, cliente: TestClient, rol: str, database_url: str
    ) -> None:
        usuario = str(uuid4())
        cabeceras = {
            "X-Usuario-Id": usuario,
            "X-Usuario-Rol": rol,
            "X-Forwarded-For": "190.24.1.7, 10.42.0.3",
            "X-Correlation-ID": "corr-denegado",
        }
        r = cliente.post("/api/catalog/zonas", json=zona(), headers=cabeceras)
        assert r.status_code == 403 and r.json()["error"] == "ROL_NO_PERMITIDO"

        async def leer(sesiones: async_sessionmaker[AsyncSession]) -> list[dict]:
            async with sesiones() as session:
                filas = await session.scalars(
                    text(
                        "SELECT sobre FROM outbox WHERE event_type = 'auditoria.registrada' "
                        "AND sobre->'payload'->>'accion' = 'ACCESS_DENIED'"
                    )
                )
                return list(filas)

        [evento] = en_la_base(database_url, leer)
        assert evento["correlation_id"] == "corr-denegado"
        assert evento["payload"] == {
            "usuario_id": usuario,
            "accion": "ACCESS_DENIED",
            "resultado": "DENEGADO",
            "detalles": {
                "rol": rol,
                "roles_permitidos": ["Entidad", "Admin"],
                "metodo": "POST",
                "ruta": "/api/catalog/zonas",
            },
            "ip_origen": "190.24.1.7",
        }

    def test_perfil_inactivo_no_se_audita(self, cliente: TestClient, database_url: str) -> None:
        # Un prestador sin perfil aprobado recibe 403 PERFIL_INACTIVO: regla del negocio, no
        # acceso indebido.
        cabeceras = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Prestador"}
        r = cliente.get("/api/catalog/prestador/perfil", headers=cabeceras)
        assert r.json()["error"] == "PERFIL_INACTIVO"

        async def contar(sesiones: async_sessionmaker[AsyncSession]) -> int:
            async with sesiones() as session:
                return await session.scalar(text("SELECT count(*) FROM outbox")) or 0

        assert en_la_base(database_url, contar) == 0

    def test_admin_tambien_puede(self, cliente: TestClient) -> None:
        cabeceras = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Admin"}
        assert cliente.post("/api/catalog/zonas", json=zona(), headers=cabeceras).status_code == 201

    def test_sin_identidad_401(self, cliente: TestClient) -> None:
        assert cliente.post("/api/catalog/zonas", json=zona()).status_code == 401


class TestObtenerYEditar:
    def test_detalle_con_etag(self, cliente: TestClient) -> None:
        creada = crear(cliente)
        r = cliente.get(f"/api/catalog/zonas/{creada['id']}", headers=ENTIDAD)
        assert r.status_code == 200 and r.headers["etag"] == '"1"'
        assert r.json() == creada
        assert cliente.get(f"/api/catalog/zonas/{uuid4()}", headers=ENTIDAD).status_code == 404

    def test_mover_el_poligono_reasigna(
        self, cliente: TestClient, servicio_id: str, database_url: str
    ) -> None:
        creada = crear(cliente)
        assert zona_del_servicio(cliente, servicio_id) == "prueba-muelle"
        r = cliente.put(
            f"/api/catalog/zonas/{creada['id']}",
            json=zona(poligono=LEJOS),
            headers=ENTIDAD | {"If-Match": '"1"'},
        )
        assert r.status_code == 200 and r.headers["etag"] == '"2"'
        assert zona_del_servicio(cliente, servicio_id) == "centro-historico"
        editada = auditorias(database_url, creada["id"])[-1]["payload"]
        assert editada["accion"] == "ZONA_EDITADA"
        assert editada["detalles"]["poligono_cambiado"] is True

    def test_concurrencia_optimista(self, cliente: TestClient) -> None:
        creada = crear(cliente)
        ruta = f"/api/catalog/zonas/{creada['id']}"
        assert cliente.put(ruta, json=zona(), headers=ENTIDAD).status_code == 428
        assert cliente.put(ruta, json=zona(), headers=ENTIDAD | {"If-Match": '"1"'}).is_success
        vieja = cliente.put(ruta, json=zona(), headers=ENTIDAD | {"If-Match": '"1"'})
        assert vieja.status_code == 409 and vieja.json()["error"] == "VERSION_DISTINTA"
        assert vieja.headers["etag"] == '"2"'

    def test_cambiar_a_un_codigo_existente(self, cliente: TestClient) -> None:
        creada = crear(cliente)
        r = cliente.put(
            f"/api/catalog/zonas/{creada['id']}",
            json=zona(codigo="minca"),
            headers=ENTIDAD | {"If-Match": '"1"'},
        )
        assert r.status_code == 409 and r.json()["error"] == "CODIGO_EXISTENTE"


class TestDesactivar:
    def test_desactivar_devuelve_los_servicios_y_repetir_no_audita(
        self, cliente: TestClient, servicio_id: str, database_url: str
    ) -> None:
        creada = crear(cliente)
        ruta = f"/api/catalog/zonas/{creada['id']}/desactivar"
        r = cliente.post(ruta, headers=ENTIDAD | {"If-Match": '"1"'})
        assert r.status_code == 200 and r.json()["activa"] is False and r.json()["version"] == 2
        assert zona_del_servicio(cliente, servicio_id) == "centro-historico"
        codigos = [z["codigo"] for z in cliente.get("/api/catalog/zonas").json()]
        assert "prueba-muelle" not in codigos

        assert cliente.post(ruta, headers=ENTIDAD | {"If-Match": '"2"'}).status_code == 200
        acciones = [e["payload"]["accion"] for e in auditorias(database_url, creada["id"])]
        assert acciones == ["ZONA_CREADA", "ZONA_DESACTIVADA"]

    def test_con_alerta_vigente_es_zona_en_uso(
        self, cliente: TestClient, database_url: str
    ) -> None:
        creada = crear(cliente)
        alerta_en(database_url, creada["id"])
        r = cliente.post(
            f"/api/catalog/zonas/{creada['id']}/desactivar",
            headers=ENTIDAD | {"If-Match": '"1"'},
        )
        assert r.status_code == 409 and r.json()["error"] == "ZONA_EN_USO"
