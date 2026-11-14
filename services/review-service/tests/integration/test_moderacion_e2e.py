"""UC29 de punta a punta: cola de moderación y decisión del Administrador.

Cada respuesta se valida contra review.yaml (tests/conftest.py) y cada evento del outbox,
contra contracts/events/ (fixture `engine`).
"""

from collections.abc import Iterator
from datetime import date
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.main import create_app

API = "/api/reviews"
ADMIN = uuid4()


@pytest.fixture
def client(database_url: str, engine: AsyncEngine) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(database_url=database_url))) as c:
        yield c


def como(usuario: UUID, rol: str, **extra: str) -> dict[str, str]:
    return {"X-Usuario-Id": str(usuario), "X-Usuario-Rol": rol, **extra}


async def ejecutar(engine: AsyncEngine, sql: str, **datos: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), datos)


async def eventos(engine: AsyncEngine, tipo: str) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        filas = await conn.execute(
            text("SELECT sobre FROM outbox WHERE event_type = :t ORDER BY creado_en"), {"t": tipo}
        )
        return [sobre for (sobre,) in filas]


async def escrita(
    client: TestClient, engine: AsyncEngine, puntuacion: int = 2
) -> tuple[UUID, UUID, str]:
    """Una reseña publicada; devuelve (turista, servicio, id)."""
    turista, servicio = uuid4(), uuid4()
    await ejecutar(
        engine,
        "INSERT INTO elegibilidad_resena VALUES (:t, :s, :v)",
        t=turista,
        s=servicio,
        v=date(2026, 11, 14),
    )
    r = client.post(
        f"{API}/resenas",
        json={"servicio_id": str(servicio), "puntuacion": puntuacion},
        headers=como(turista, "Turista"),
    )
    assert r.status_code == 201, r.text
    return turista, servicio, r.json()["id"]


def reportar(client: TestClient, resena: str, veces: int, motivo: str = "SPAM") -> None:
    for _ in range(veces):
        r = client.post(
            f"{API}/resenas/{resena}/reportes",
            json={"motivo": motivo},
            headers=como(uuid4(), "Turista"),
        )
        assert r.status_code == 204, r.text


def moderar(
    client: TestClient, resena: str, version: int | None, decision: str, motivo: str | None = None
) -> Any:
    cabeceras = como(ADMIN, "Admin", **{"X-Forwarded-For": "181.0.0.9"})
    if version is not None:
        cabeceras["If-Match"] = f'"{version}"'
    return client.post(
        f"{API}/resenas/{resena}/moderacion",
        json={"decision": decision, "motivo": motivo},
        headers=cabeceras,
    )


def cola(client: TestClient, **params: Any) -> dict[str, Any]:
    r = client.get(f"{API}/moderacion/resenas", params=params, headers=como(ADMIN, "Admin"))
    assert r.status_code == 200, r.text
    return r.json()


class TestCola:
    async def test_orden_y_contenido(self, client: TestClient, engine: AsyncEngine) -> None:
        _, _, un_reporte = await escrita(client, engine)
        reportar(client, un_reporte, 1)
        _, _, dos_reportes = await escrita(client, engine)
        reportar(client, dos_reportes, 2, motivo="OFENSIVO")
        turista, _, en_revision = await escrita(client, engine)
        reportar(client, en_revision, 3)
        await escrita(client, engine)  # sin reportes: no entra

        datos = cola(client)

        assert datos["total"] == 3
        assert [i["id"] for i in datos["items"]] == [en_revision, dos_reportes, un_reporte]
        primero = datos["items"][0]
        assert primero["estado"] == "EN_REVISION" and primero["turista_id"] == str(turista)
        assert len(primero["reportes"]) == 3
        reporte = datos["items"][1]["reportes"][0]
        assert reporte["motivo"] == "OFENSIVO" and reporte["motivo_etiqueta"] == "Ofensivo"
        assert reporte["rol_reportante"] == "Turista" and reporte["es_dueno"] is False
        assert [i["id"] for i in cola(client, estado="EN_REVISION")["items"]] == [en_revision]

    def test_solo_el_admin_y_se_audita(self, client: TestClient) -> None:
        r = client.get(f"{API}/moderacion/resenas", headers=como(uuid4(), "Turista"))
        assert (r.status_code, r.json()["error"]) == (403, "ROL_NO_PERMITIDO")


class TestPublicar:
    async def test_una_en_revision_vuelve_sin_evento_y_sale_de_la_cola(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, servicio, resena = await escrita(client, engine)
        reportar(client, resena, 3)

        r = moderar(client, resena, 2, "PUBLICAR")

        assert r.status_code == 200 and r.headers["ETag"] == '"3"'
        assert r.json()["estado"] == "PUBLICADA" and r.json()["reportes"] == []
        assert cola(client)["total"] == 0
        listado = client.get(f"{API}/servicios/{servicio}/resenas").json()
        assert listado["total"] == 1
        assert len(await eventos(engine, "resena.publicada")) == 1  # solo el de crearla
        [auditoria] = await eventos(engine, "auditoria.registrada")
        assert auditoria["payload"]["accion"] == "MODERACION"
        assert auditoria["payload"]["usuario_id"] == str(ADMIN)
        assert auditoria["payload"]["ip_origen"] == "181.0.0.9"
        assert auditoria["payload"]["detalles"] == {
            "resena_id": resena,
            "servicio_id": str(servicio),
            "decision": "PUBLICAR",
            "motivo": None,
            "estado_anterior": "EN_REVISION",
            "estado_nuevo": "PUBLICADA",
            "reportes_resueltos": 3,
        }

    async def test_despues_cuentan_solo_los_reportes_nuevos(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, _, resena = await escrita(client, engine)
        ya_reporto = uuid4()
        client.post(
            f"{API}/resenas/{resena}/reportes",
            json={"motivo": "SPAM"},
            headers=como(ya_reporto, "Turista"),
        )
        moderar(client, resena, 1, "PUBLICAR")

        repetido = client.post(
            f"{API}/resenas/{resena}/reportes",
            json={"motivo": "SPAM"},
            headers=como(ya_reporto, "Turista"),
        )
        reportar(client, resena, 1)

        assert repetido.status_code == 409
        [item] = cola(client)["items"]
        assert len(item["reportes"]) == 1

    async def test_una_oculta_vuelve_a_contar(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, servicio, resena = await escrita(client, engine)
        moderar(client, resena, 1, "OCULTAR", "Datos personales")

        r = moderar(client, resena, 2, "PUBLICAR", "Se revisó con el turista")

        assert r.status_code == 200
        publicadas = await eventos(engine, "resena.publicada")
        assert len(publicadas) == 2 and publicadas[1]["payload"]["resena_id"] == resena
        assert client.get(f"{API}/servicios/{servicio}/resumen").json()["total"] == 1


class TestOcultar:
    async def test_la_quita_del_promedio_y_de_la_lista(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista, servicio, resena = await escrita(client, engine, puntuacion=1)
        reportar(client, resena, 1)

        r = moderar(client, resena, 1, "OCULTAR", " Ofensiva ")

        assert r.status_code == 200 and r.json()["estado"] == "OCULTA"
        [ocultada] = await eventos(engine, "resena.ocultada")
        assert ocultada["payload"] == {
            "resena_id": resena,
            "servicio_id": str(servicio),
            "turista_id": str(turista),
            "puntuacion": 1,
            "moderada_por": str(ADMIN),
            "motivo": "Ofensiva",
        }
        assert client.get(f"{API}/servicios/{servicio}/resumen").json()["total"] == 0
        assert client.get(f"{API}/resenas/{resena}").status_code == 404
        mias = client.get(f"{API}/turista/resenas", headers=como(turista, "Turista")).json()
        assert mias["items"][0]["estado"] == "OCULTA"

    async def test_sin_motivo(self, client: TestClient, engine: AsyncEngine) -> None:
        _, _, resena = await escrita(client, engine)
        r = moderar(client, resena, 1, "OCULTAR")
        assert (r.status_code, r.json()["error"]) == (400, "VALIDACION")
        assert await eventos(engine, "auditoria.registrada") == []

    async def test_ocultar_una_oculta_no_cambia_pero_se_audita(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, _, resena = await escrita(client, engine)
        moderar(client, resena, 1, "OCULTAR", "Spam")

        r = moderar(client, resena, 2, "OCULTAR", "Otra vez")

        assert r.status_code == 200 and r.headers["ETag"] == '"2"'
        assert len(await eventos(engine, "resena.ocultada")) == 1
        assert len(await eventos(engine, "auditoria.registrada")) == 2


class TestErrores:
    async def test_un_turista_no_modera(self, client: TestClient, engine: AsyncEngine) -> None:
        turista, _, resena = await escrita(client, engine)
        r = client.post(
            f"{API}/resenas/{resena}/moderacion",
            json={"decision": "PUBLICAR"},
            headers=como(turista, "Turista", **{"If-Match": '"1"'}),
        )
        assert (r.status_code, r.json()["error"]) == (403, "ROL_NO_PERMITIDO")
        [auditoria] = await eventos(engine, "auditoria.registrada")
        assert auditoria["payload"]["accion"] == "ACCESS_DENIED"

    def test_una_que_no_existe(self, client: TestClient) -> None:
        r = moderar(client, str(uuid4()), 1, "PUBLICAR")
        assert (r.status_code, r.json()["error"]) == (404, "NO_ENCONTRADO")

    async def test_sin_if_match(self, client: TestClient, engine: AsyncEngine) -> None:
        _, _, resena = await escrita(client, engine)
        r = moderar(client, resena, None, "PUBLICAR")
        assert (r.status_code, r.json()["error"]) == (428, "FALTA_IF_MATCH")

    async def test_un_reporte_la_cambio_antes(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, _, resena = await escrita(client, engine)
        reportar(client, resena, 3)  # pasa a revisión: versión 2

        r = moderar(client, resena, 1, "OCULTAR", "Spam")

        assert (r.status_code, r.json()["error"]) == (409, "VERSION_DISTINTA")
        assert r.headers["ETag"] == '"2"'

    async def test_decision_desconocida(self, client: TestClient, engine: AsyncEngine) -> None:
        _, _, resena = await escrita(client, engine)
        r = moderar(client, resena, 1, "BORRAR")
        assert (r.status_code, r.json()["error"]) == (400, "VALIDACION")
