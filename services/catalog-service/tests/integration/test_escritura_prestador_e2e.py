"""Escritura del prestador completa: HTTP → caso de uso → PostGIS, outbox y Valkey reales."""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_geocodificador
from app.application.dto.candidato_direccion import CandidatoDireccion
from app.config import get_settings
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.idioma import Idioma
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.main import create_app

pytestmark = pytest.mark.integration

BASE_IMAGENES = "http://imagenes.test/catalogo-imagenes"
CENTRO = {"lat": 11.2420, "lon": -74.2110}
MINCA = {"lat": 11.1426, "lon": -74.1178}


@dataclass
class Prestador:
    perfil: PrestadorPerfil

    @property
    def cabeceras(self) -> dict[str, str]:
        return {"X-Usuario-Id": str(self.perfil.usuario_id), "X-Usuario-Rol": "Prestador"}

    def imagen(self) -> str:
        return f"{BASE_IMAGENES}/{self.perfil.id}/{uuid4()}.webp"


def en_la_base(
    url: str, operacion: Callable[[async_sessionmaker[AsyncSession]], Awaitable[Any]]
) -> Any:
    """Las pruebas son síncronas (TestClient): cada acceso directo usa su propio engine y loop."""

    async def correr() -> Any:
        engine = build_engine(url)
        try:
            return await operacion(build_session_factory(engine))
        finally:
            await engine.dispose()

    return asyncio.run(correr())


def aprobar(url: str, activo: bool = True) -> Prestador:
    """Simula `prestador.aprobado` (el consumidor llega en un paso posterior)."""
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Turismo Sierra")
    if not activo:
        perfil.suspender()

    async def guardar(sesiones: async_sessionmaker[AsyncSession]) -> None:
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.prestadores.guardar(perfil)
            await uow.confirmar()

    en_la_base(url, guardar)
    return Prestador(perfil)


def eventos(url: str, servicio_id: str) -> list[dict]:
    async def leer(sesiones: async_sessionmaker[AsyncSession]) -> list[dict]:
        async with sesiones() as session:
            filas = await session.scalars(
                text(
                    "SELECT sobre FROM outbox WHERE sobre->'payload'->>'servicio_id' = :id "
                    "ORDER BY creado_en, (sobre->'payload'->>'version')::int"
                ),
                {"id": servicio_id},
            )
            return list(filas)

    return en_la_base(url, leer)


def cuerpo(prestador: Prestador, **cambios: object) -> dict:
    return {
        "nombre": {"es": "Tour del café", "en": "Coffee tour"},
        "descripcion": {"es": "Recorrido por fincas"},
        "tipo": "EXPERIENCIA_GASTRONOMICA",
        "unidad_tarifa": "POR_PERSONA",
        "atributos": {"experiencia": {"duracion_minutos": 180, "nivel_fisico": "BAJO"}},
        "ubicacion": CENTRO,
        "tarifa_base": 85000,
        "capacidad_aforo_diario": 20,
        "imagenes_urls": [prestador.imagen()],
    } | cambios


class GeocodificadorFalso:
    async def buscar(self, direccion: str, idioma: Idioma) -> list[CandidatoDireccion]:
        return [CandidatoDireccion(Coordenada(lat=11.24, lon=-74.21), f"{direccion} ({idioma})")]


@pytest.fixture
def cliente(database_url: str, valkey_url: str, engine: object) -> Iterator[TestClient]:
    # `engine` limpia las tablas al terminar.
    settings = get_settings().model_copy(
        update={
            "database_url": database_url,
            "valkey_url": valkey_url,
            "imagenes_url_publica": BASE_IMAGENES,
            "s3_access_key": "prueba",
            "s3_secret_key": "prueba",
        }
    )
    app = create_app(settings)
    app.dependency_overrides[get_geocodificador] = GeocodificadorFalso
    with TestClient(app) as c:
        yield c


@pytest.fixture
def prestador(database_url: str, cliente: TestClient) -> Prestador:
    return aprobar(database_url)


def registrar(cliente: TestClient, prestador: Prestador, **cambios: object) -> dict:
    r = cliente.post(
        "/api/catalog/servicios", json=cuerpo(prestador, **cambios), headers=prestador.cabeceras
    )
    assert r.status_code == 201, r.text
    return r.json()


class TestRegistrar:
    def test_crea_asigna_zona_publica_evento_e_invalida_cache(
        self, cliente: TestClient, prestador: Prestador, database_url: str
    ) -> None:
        assert cliente.get("/api/catalog/buscar").json()["total"] == 0  # queda en caché
        r = cliente.post(
            "/api/catalog/servicios",
            json=cuerpo(prestador),
            headers=prestador.cabeceras | {"X-Correlation-ID": "corr-registro"},
        )
        assert r.status_code == 201 and r.headers["etag"] == '"1"'
        servicio = r.json()
        assert servicio["zona"]["codigo"] == "centro-historico"
        assert servicio["nombre"] == {"es": "Tour del café", "en": "Coffee tour"}
        assert (servicio["activo"], servicio["version"]) == (True, 1)
        # La caché se invalidó: la búsqueda ya lo ve.
        assert cliente.get("/api/catalog/buscar").json()["total"] == 1

        [evento] = eventos(database_url, servicio["id"])
        assert evento["event_type"] == "servicio.publicado"
        assert evento["producer"] == "catalog-service"
        assert evento["correlation_id"] == "corr-registro"
        assert evento["payload"] == {
            "servicio_id": servicio["id"],
            "prestador_id": str(prestador.perfil.id),
            "prestador_usuario_id": str(prestador.perfil.usuario_id),
            "capacidad_aforo_diario": 20,
            "tarifa_base": 85000.0,
            "activo": True,
            "version": 1,
        }

    def test_imagen_de_otro_prestador_se_rechaza(
        self, cliente: TestClient, prestador: Prestador, database_url: str
    ) -> None:
        otro = aprobar(database_url)
        r = cliente.post(
            "/api/catalog/servicios",
            json=cuerpo(prestador, imagenes_urls=[otro.imagen()]),
            headers=prestador.cabeceras | {"Accept-Language": "en"},
        )
        assert r.status_code == 400 and r.json()["error"] == "VALIDACION"
        assert (
            r.json()["message"] == "Images must be uploaded with the URL provided by the platform."
        )

    def test_idempotency_key_no_duplica(
        self, cliente: TestClient, prestador: Prestador, database_url: str
    ) -> None:
        cabeceras = prestador.cabeceras | {"Idempotency-Key": str(uuid4())}
        datos = cuerpo(prestador)
        primera = cliente.post("/api/catalog/servicios", json=datos, headers=cabeceras)
        segunda = cliente.post("/api/catalog/servicios", json=datos, headers=cabeceras)
        assert primera.status_code == segunda.status_code == 201
        assert primera.json() == segunda.json() and segunda.headers["idempotent-replayed"] == "true"
        assert segunda.headers["etag"] == '"1"'
        listado = cliente.get(
            "/api/catalog/prestador/servicios", headers=prestador.cabeceras
        ).json()
        assert listado["total"] == 1
        assert len(eventos(database_url, primera.json()["id"])) == 1


class TestEditar:
    def test_concurrencia_optimista(self, cliente: TestClient, prestador: Prestador) -> None:
        servicio = registrar(cliente, prestador)
        url = f"/api/catalog/servicios/{servicio['id']}"
        movido = cuerpo(prestador, ubicacion=MINCA, capacidad_aforo_diario=30)

        sin_version = cliente.put(url, json=movido, headers=prestador.cabeceras)
        assert sin_version.status_code == 428 and sin_version.json()["error"] == "FALTA_IF_MATCH"

        r = cliente.put(url, json=movido, headers=prestador.cabeceras | {"If-Match": '"1"'})
        assert r.status_code == 200 and r.headers["etag"] == '"2"'
        assert r.json()["zona"]["codigo"] == "minca"  # la zona sigue a la ubicación

        viejo = cliente.put(url, json=movido, headers=prestador.cabeceras | {"If-Match": '"1"'})
        assert viejo.status_code == 409 and viejo.json()["error"] == "VERSION_DISTINTA"
        assert viejo.headers["etag"] == '"2"'

    def test_servicio_ajeno_es_404(
        self, cliente: TestClient, prestador: Prestador, database_url: str
    ) -> None:
        servicio = registrar(cliente, prestador)
        otro = aprobar(database_url)
        r = cliente.put(
            f"/api/catalog/servicios/{servicio['id']}",
            json=cuerpo(otro),
            headers=otro.cabeceras | {"If-Match": '"1"'},
        )
        assert r.status_code == 404 and r.json()["error"] == "NO_ENCONTRADO"


class TestEstado:
    def test_desactivar_oculta_y_repetir_no_publica(
        self, cliente: TestClient, prestador: Prestador, database_url: str
    ) -> None:
        servicio = registrar(cliente, prestador)
        base = f"/api/catalog/servicios/{servicio['id']}"
        r = cliente.post(f"{base}/desactivar", headers=prestador.cabeceras | {"If-Match": '"1"'})
        assert r.status_code == 200 and r.json()["activo"] is False and r.headers["etag"] == '"2"'
        assert cliente.get(base).status_code == 404  # fuera del catálogo público

        otra_vez = cliente.post(
            f"{base}/desactivar", headers=prestador.cabeceras | {"If-Match": '"2"'}
        )
        assert otra_vez.status_code == 200 and otra_vez.headers["etag"] == '"2"'
        assert [e["payload"]["activo"] for e in eventos(database_url, servicio["id"])] == [
            True,
            False,
        ]

        r = cliente.post(f"{base}/reactivar", headers=prestador.cabeceras | {"If-Match": '"2"'})
        assert r.json()["activo"] is True and cliente.get(base).status_code == 200

    def test_el_panel_muestra_los_inactivos(
        self, cliente: TestClient, prestador: Prestador
    ) -> None:
        servicio = registrar(cliente, prestador)
        cliente.post(
            f"/api/catalog/servicios/{servicio['id']}/desactivar",
            headers=prestador.cabeceras | {"If-Match": '"1"'},
        )
        registrar(cliente, prestador, nombre={"es": "Otro"})
        panel = cliente.get(
            "/api/catalog/prestador/servicios",
            headers=prestador.cabeceras | {"Accept-Language": "en"},
        ).json()
        assert panel["total"] == 2
        assert [s["activo"] for s in panel["items"]] == [True, False]  # el más reciente primero
        assert panel["items"][1]["categoria_etiqueta"] == "Food & dining"


class TestAcceso:
    def test_sin_cabeceras_es_401(self, cliente: TestClient, prestador: Prestador) -> None:
        r = cliente.post("/api/catalog/servicios", json=cuerpo(prestador))
        assert r.status_code == 401 and r.json()["error"] == "NO_AUTENTICADO"

    def test_turista_es_403(self, cliente: TestClient, prestador: Prestador) -> None:
        cabeceras = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Turista"}
        r = cliente.post("/api/catalog/servicios", json=cuerpo(prestador), headers=cabeceras)
        assert r.status_code == 403 and r.json()["error"] == "ROL_NO_PERMITIDO"

    def test_prestador_sin_aprobar_es_perfil_inactivo(self, cliente: TestClient) -> None:
        cabeceras = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Prestador"}
        r = cliente.get("/api/catalog/prestador/perfil", headers=cabeceras)
        assert r.status_code == 403 and r.json()["error"] == "PERFIL_INACTIVO"

    def test_suspendido_ve_su_perfil_pero_no_escribe(
        self, cliente: TestClient, database_url: str
    ) -> None:
        suspendido = aprobar(database_url, activo=False)
        perfil = cliente.get("/api/catalog/prestador/perfil", headers=suspendido.cabeceras)
        assert perfil.status_code == 200 and perfil.json()["activo"] is False
        r = cliente.post(
            "/api/catalog/servicios", json=cuerpo(suspendido), headers=suspendido.cabeceras
        )
        assert r.status_code == 403 and r.json()["error"] == "PERFIL_INACTIVO"


class TestPerfilImagenesYDirecciones:
    def test_editar_perfil(self, cliente: TestClient, prestador: Prestador) -> None:
        r = cliente.get("/api/catalog/prestador/perfil", headers=prestador.cabeceras)
        assert r.headers["etag"] == '"1"'
        datos = {"telefono": "3001234567", "politica_cancelacion": {"es": "Gratis 24 h antes"}}
        r = cliente.put(
            "/api/catalog/prestador/perfil",
            json=datos,
            headers=prestador.cabeceras | {"If-Match": '"1"'},
        )
        assert r.status_code == 200 and r.headers["etag"] == '"2"'
        assert r.json()["politica_cancelacion"] == {"es": "Gratis 24 h antes", "en": None}

    def test_url_de_subida_en_la_carpeta_del_prestador(
        self, cliente: TestClient, prestador: Prestador
    ) -> None:
        r = cliente.post(
            "/api/catalog/prestador/imagenes",
            json={"content_type": "image/webp", "tamano_bytes": 120_000},
            headers=prestador.cabeceras,
        )
        assert r.status_code == 201
        subida = r.json()
        assert subida["url_publica"].startswith(f"{BASE_IMAGENES}/{prestador.perfil.id}/")
        assert subida["url_publica"].endswith(".webp")
        assert "X-Amz-Signature=" in subida["subida_url"]
        demasiado = cliente.post(
            "/api/catalog/prestador/imagenes",
            json={"content_type": "image/gif", "tamano_bytes": 10},
            headers=prestador.cabeceras,
        )
        assert demasiado.status_code == 400

    def test_geocodificar(self, cliente: TestClient, prestador: Prestador) -> None:
        r = cliente.get(
            "/api/catalog/geocodificar",
            params={"direccion": "Parque de los Novios"},
            headers=prestador.cabeceras | {"Accept-Language": "en"},
        )
        assert r.status_code == 200
        assert r.json() == [{"lat": 11.24, "lon": -74.21, "etiqueta": "Parque de los Novios (en)"}]


PAGOS_SIN_SENAL = {
    "senal_internet": "SIN_SENAL",
    "medios_pago": ["EFECTIVO"],
    "recomendacion_dinero": "EFECTIVO",
    "credito": {"ofrece": True, "plazo_dias": 3, "condiciones": {"es": "Pagas por Nequi"}},
    "cajeros": {"hay_cerca": False, "referencia": {"es": "Parque de Minca"}, "distancia_km": 8},
}


class TestTipoYAtributos:
    def test_transporte_con_pagos_se_guarda_y_se_relee(
        self, cliente: TestClient, prestador: Prestador
    ) -> None:
        atributos = {
            "comunes": {"idiomas_atencion": ["es", "en"], "apto_ninos": True},
            "transporte": {
                "origen": {"es": "Taganga"},
                "destino": {"es": "Playa Cristal", "en": "Cristal Beach"},
                "duracion_minutos": 40,
                "capacidad_vehiculo": 12,
                "horarios_salida": ["10:00", "08:00"],
                "incluye_chaleco_salvavidas": True,
            },
            "pagos": PAGOS_SIN_SENAL,
        }
        servicio = registrar(
            cliente,
            prestador,
            tipo="TRANSPORTE_MARITIMO",
            unidad_tarifa="POR_PERSONA",
            atributos=atributos,
        )
        assert (servicio["tipo"], servicio["categoria"]) == ("TRANSPORTE_MARITIMO", "TRANSPORTE")
        assert servicio["tipo_etiqueta"] == "Transporte en lancha"
        assert servicio["unidad_tarifa_etiqueta"] == "por persona"
        assert servicio["atributos"]["transporte"]["horarios_salida"] == ["08:00", "10:00"]
        assert servicio["atributos"]["pagos"]["credito"]["plazo_dias"] == 3
        assert servicio["atributos"]["pagos"]["cajeros"]["distancia_km"] == 8

        panel = cliente.get(
            "/api/catalog/prestador/servicios",
            headers=prestador.cabeceras | {"Accept-Language": "en"},
        ).json()["items"][0]
        assert panel["atributos"] == servicio["atributos"]
        assert panel["categoria_etiqueta"] == "Transport"

    def test_falta_el_bloque_principal(self, cliente: TestClient, prestador: Prestador) -> None:
        r = cliente.post(
            "/api/catalog/servicios",
            json=cuerpo(prestador, tipo="HOSTAL", atributos={}),
            headers=prestador.cabeceras,
        )
        assert r.status_code == 400 and r.json()["error"] == "VALIDACION"
        assert r.json()["message"] == "Para el tipo HOSTAL hay que llenar «atributos.alojamiento»."

    def test_bloque_de_otro_tipo(self, cliente: TestClient, prestador: Prestador) -> None:
        atributos = {
            "experiencia": {"duracion_minutos": 60, "nivel_fisico": "BAJO"},
            "alojamiento": {
                "check_in": "14:00",
                "check_out": "11:00",
                "habitaciones": [{"tipo": "PRIVADA", "capacidad_personas": 2}],
            },
        }
        r = cliente.post(
            "/api/catalog/servicios",
            json=cuerpo(prestador, atributos=atributos),
            headers=prestador.cabeceras,
        )
        assert r.status_code == 400
        assert "atributos.alojamiento" in r.json()["message"]

    def test_recomendacion_que_no_coincide_con_los_medios(
        self, cliente: TestClient, prestador: Prestador
    ) -> None:
        atributos = {
            "experiencia": {"duracion_minutos": 60, "nivel_fisico": "BAJO"},
            "pagos": PAGOS_SIN_SENAL | {"recomendacion_dinero": "DIGITAL"},
        }
        r = cliente.post(
            "/api/catalog/servicios",
            json=cuerpo(prestador, atributos=atributos),
            headers=prestador.cabeceras,
        )
        assert r.status_code == 400
        assert "medios de pago" in r.json()["message"]

    def test_grupo_mayor_que_el_aforo(self, cliente: TestClient, prestador: Prestador) -> None:
        atributos = {
            "experiencia": {"duracion_minutos": 60, "nivel_fisico": "BAJO", "grupo_maximo": 50}
        }
        r = cliente.post(
            "/api/catalog/servicios",
            json=cuerpo(prestador, atributos=atributos),
            headers=prestador.cabeceras,
        )
        assert r.status_code == 400

    def test_campo_desconocido_en_un_bloque(
        self, cliente: TestClient, prestador: Prestador
    ) -> None:
        atributos = {"experiencia": {"duracion_minutos": 60, "nivel_fisico": "BAJO", "x": 1}}
        r = cliente.post(
            "/api/catalog/servicios",
            json=cuerpo(prestador, atributos=atributos),
            headers=prestador.cabeceras,
        )
        assert r.status_code == 400

    def test_la_categoria_ya_no_se_envia(self, cliente: TestClient, prestador: Prestador) -> None:
        r = cliente.post(
            "/api/catalog/servicios",
            json=cuerpo(prestador, categoria="PLAYA"),
            headers=prestador.cabeceras,
        )
        assert r.status_code == 400
