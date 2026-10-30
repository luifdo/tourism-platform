"""UC39 de punta a punta: reportar una reseña.

Cada respuesta se valida contra review.yaml (tests/conftest.py).
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


@pytest.fixture
def client(database_url: str, engine: AsyncEngine) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(database_url=database_url))) as c:
        yield c


def como(usuario: UUID, rol: str = "Turista", version: str | None = None) -> dict[str, str]:
    cabeceras = {"X-Usuario-Id": str(usuario), "X-Usuario-Rol": rol}
    return cabeceras | ({"If-Match": version} if version else {})


async def ejecutar(engine: AsyncEngine, sql: str, **datos: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), datos)


async def escenario(client: TestClient, engine: AsyncEngine) -> tuple[UUID, UUID, UUID, str]:
    """Un turista reseña un servicio; devuelve (turista, dueño, servicio, id de la reseña)."""
    turista, dueno, servicio = uuid4(), uuid4(), uuid4()
    await ejecutar(
        engine,
        "INSERT INTO elegibilidad_resena VALUES (:t, :s, :v)",
        t=turista,
        s=servicio,
        v=date(2026, 11, 14),
    )
    await ejecutar(engine, "INSERT INTO servicio_dueno VALUES (:s, :d, 1)", s=servicio, d=dueno)
    r = client.post(
        f"{API}/resenas",
        json={"servicio_id": str(servicio), "puntuacion": 2, "comentario": "Malo"},
        headers=como(turista),
    )
    assert r.status_code == 201, r.text
    return turista, dueno, servicio, r.json()["id"]


def reportar(
    client: TestClient,
    resena: str,
    usuario: UUID | None = None,
    rol: str = "Turista",
    **cuerpo: Any,
) -> Any:
    return client.post(
        f"{API}/resenas/{resena}/reportes",
        json={"motivo": "SPAM"} | cuerpo,
        headers=como(usuario or uuid4(), rol),
    )


def visibles(client: TestClient, servicio: UUID) -> int:
    return client.get(f"{API}/servicios/{servicio}/resenas").json()["total"]


async def estado(engine: AsyncEngine, resena: str) -> tuple[str, int, int]:
    async with engine.connect() as conn:
        fila = (
            await conn.execute(
                text("SELECT estado, reportes_pendientes, version FROM resena WHERE id = :id"),
                {"id": resena},
            )
        ).one()
    return fila.estado, fila.reportes_pendientes, fila.version


class TestReportar:
    async def test_dos_reportes_no_la_ocultan_y_el_tercero_si(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, _, servicio, resena = await escenario(client, engine)

        for _ in range(2):
            r = reportar(client, resena)
            assert r.status_code == 204 and r.content == b""
        assert visibles(client, servicio) == 1
        assert await estado(engine, resena) == ("PUBLICADA", 2, 1)

        assert reportar(client, resena, motivo="FALSO").status_code == 204
        assert await estado(engine, resena) == ("EN_REVISION", 3, 2)
        assert visibles(client, servicio) == 0
        # La nota sigue contando mientras está en revisión.
        assert client.get(f"{API}/servicios/{servicio}/resumen").json()["total"] == 1

    async def test_el_reporte_del_dueno_la_pasa_a_revision(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, dueno, _, resena = await escenario(client, engine)

        assert reportar(client, resena, dueno, "Prestador").status_code == 204

        assert await estado(engine, resena) == ("EN_REVISION", 1, 2)

    async def test_otro_prestador_cuenta_como_uno_mas(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, _, _, resena = await escenario(client, engine)

        assert reportar(client, resena, uuid4(), "Prestador").status_code == 204

        assert await estado(engine, resena) == ("PUBLICADA", 1, 1)

    async def test_el_autor_sigue_editando_tras_un_reporte(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista, _, _, resena = await escenario(client, engine)
        reportar(client, resena)

        r = client.put(
            f"{API}/resenas/{resena}", json={"puntuacion": 3}, headers=como(turista, version="1")
        )

        assert r.status_code == 200

    async def test_un_usuario_reporta_una_sola_vez(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, _, _, resena = await escenario(client, engine)
        usuario = uuid4()
        reportar(client, resena, usuario)

        r = reportar(client, resena, usuario)

        assert (r.status_code, r.json()["error"]) == (409, "YA_REPORTADA")
        assert await estado(engine, resena) == ("PUBLICADA", 1, 1)

    async def test_la_propia_no(self, client: TestClient, engine: AsyncEngine) -> None:
        turista, _, _, resena = await escenario(client, engine)
        r = reportar(client, resena, turista)
        assert (r.status_code, r.json()["error"]) == (403, "RESENA_PROPIA")

    async def test_solo_publicadas(self, client: TestClient, engine: AsyncEngine) -> None:
        _, _, _, resena = await escenario(client, engine)
        await ejecutar(engine, "UPDATE resena SET estado = 'EN_REVISION' WHERE id = :id", id=resena)

        for destino in (resena, str(uuid4())):
            r = reportar(client, destino)
            assert (r.status_code, r.json()["error"]) == (404, "NO_ENCONTRADO")

    async def test_el_admin_no_reporta_y_se_audita(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, _, _, resena = await escenario(client, engine)

        r = reportar(client, resena, rol="Admin")

        assert (r.status_code, r.json()["error"]) == (403, "ROL_NO_PERMITIDO")
        async with engine.connect() as conn:
            assert (
                await conn.scalar(
                    text("SELECT count(*) FROM outbox WHERE event_type = 'auditoria.registrada'")
                )
                == 1
            )

    @pytest.mark.parametrize(
        "cuerpo",
        [
            {"motivo": "OTRO"},
            {"motivo": "OTRO", "detalle": "   "},
            {"motivo": "ABURRIDA"},
            {"motivo": "SPAM", "detalle": "x" * 501},
            {"motivo": "SPAM", "extra": 1},
        ],
    )
    async def test_datos_invalidos(
        self, client: TestClient, engine: AsyncEngine, cuerpo: dict[str, Any]
    ) -> None:
        _, _, _, resena = await escenario(client, engine)
        r = reportar(client, resena, **cuerpo)
        assert (r.status_code, r.json()["error"]) == (400, "VALIDACION")

    async def test_otro_con_detalle(self, client: TestClient, engine: AsyncEngine) -> None:
        _, _, _, resena = await escenario(client, engine)
        r = reportar(client, resena, motivo="OTRO", detalle="Publicidad de otro negocio")
        assert r.status_code == 204


class TestLimite:
    async def test_el_once_en_una_hora_espera(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        usuario = uuid4()
        for _ in range(10):
            _, _, _, resena = await escenario(client, engine)
            assert reportar(client, resena, usuario).status_code == 204
        _, _, _, otra = await escenario(client, engine)

        r = reportar(client, otra, usuario)
        inexistente = reportar(client, str(uuid4()), usuario)

        assert (r.status_code, r.json()["error"]) == (429, "DEMASIADOS_REPORTES")
        assert 3500 <= int(r.headers["Retry-After"]) <= 3600
        # El límite va antes que la reseña: no sirve para averiguar cuáles existen.
        assert inexistente.status_code == 429
        assert await estado(engine, otra) == ("PUBLICADA", 0, 1)
