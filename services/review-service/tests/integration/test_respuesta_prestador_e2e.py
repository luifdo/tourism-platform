"""UC21 de punta a punta: el prestador dueño responde una reseña.

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


def como(usuario: UUID, rol: str, version: str | None = None) -> dict[str, str]:
    cabeceras = {"X-Usuario-Id": str(usuario), "X-Usuario-Rol": rol}
    return cabeceras | ({"If-Match": version} if version else {})


async def ejecutar(engine: AsyncEngine, sql: str, **datos: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), datos)


async def escenario(
    client: TestClient, engine: AsyncEngine, con_dueno: bool = True
) -> tuple[UUID, UUID, str]:
    """Un turista reseña un servicio; devuelve (turista, prestador dueño, id de la reseña)."""
    turista, prestador, servicio = uuid4(), uuid4(), uuid4()
    await ejecutar(
        engine,
        "INSERT INTO elegibilidad_resena VALUES (:t, :s, :v)",
        t=turista,
        s=servicio,
        v=date(2026, 11, 14),
    )
    if con_dueno:
        await ejecutar(
            engine, "INSERT INTO servicio_dueno VALUES (:s, :p, 1)", s=servicio, p=prestador
        )
    r = client.post(
        f"{API}/resenas",
        json={"servicio_id": str(servicio), "puntuacion": 3, "comentario": "Regular"},
        headers=como(turista, "Turista"),
    )
    assert r.status_code == 201, r.text
    return turista, prestador, r.json()["id"]


def responder(
    client: TestClient, resena: str, prestador: UUID, version: str | None, texto: str
) -> Any:
    return client.put(
        f"{API}/resenas/{resena}/respuesta",
        json={"texto": texto},
        headers=como(prestador, "Prestador", version),
    )


class TestResponder:
    async def test_crea_y_reemplaza_la_respuesta(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, prestador, resena = await escenario(client, engine)

        primera = responder(client, resena, prestador, '"1"', "Gracias por venir")
        segunda = responder(client, resena, prestador, '"2"', "Gracias, te esperamos")

        assert primera.status_code == 200 and primera.headers["ETag"] == '"2"'
        assert segunda.headers["ETag"] == '"3"'
        assert segunda.json()["respuesta"]["texto"] == "Gracias, te esperamos"
        assert segunda.json()["estado"] == "PUBLICADA"
        publica = client.get(f"{API}/resenas/{resena}").json()
        assert publica["respuesta"]["texto"] == "Gracias, te esperamos"

    async def test_en_revision_si_se_responde(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        _, prestador, resena = await escenario(client, engine)
        await ejecutar(engine, "UPDATE resena SET estado = 'EN_REVISION' WHERE id = :id", id=resena)

        r = responder(client, resena, prestador, '"1"', "Nuestra versión de lo ocurrido")

        assert r.status_code == 200 and r.json()["estado"] == "EN_REVISION"

    async def test_oculta_no_se_responde(self, client: TestClient, engine: AsyncEngine) -> None:
        _, prestador, resena = await escenario(client, engine)
        await ejecutar(engine, "UPDATE resena SET estado = 'OCULTA' WHERE id = :id", id=resena)

        r = responder(client, resena, prestador, '"1"', "Hola")

        assert (r.status_code, r.json()["error"]) == (409, "RESENA_EN_MODERACION")

    @pytest.mark.parametrize("con_dueno", [True, False])
    async def test_solo_el_dueno_del_servicio(
        self, client: TestClient, engine: AsyncEngine, con_dueno: bool
    ) -> None:
        _, _, resena = await escenario(client, engine, con_dueno=con_dueno)

        r = responder(client, resena, uuid4(), '"1"', "No soy el dueño")

        assert (r.status_code, r.json()["error"]) == (403, "NO_ES_DUENO")

    async def test_un_turista_no_responde_y_se_audita(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista, _, resena = await escenario(client, engine)

        r = client.put(
            f"{API}/resenas/{resena}/respuesta",
            json={"texto": "Me respondo"},
            headers=como(turista, "Turista", '"1"'),
        )

        assert (r.status_code, r.json()["error"]) == (403, "ROL_NO_PERMITIDO")
        async with engine.connect() as conn:
            assert (
                await conn.scalar(
                    text("SELECT count(*) FROM outbox WHERE event_type = 'auditoria.registrada'")
                )
                == 1
            )

    async def test_sin_if_match(self, client: TestClient, engine: AsyncEngine) -> None:
        _, prestador, resena = await escenario(client, engine)
        r = responder(client, resena, prestador, None, "Gracias")
        assert (r.status_code, r.json()["error"]) == (428, "FALTA_IF_MATCH")

    async def test_el_turista_edito_antes(self, client: TestClient, engine: AsyncEngine) -> None:
        turista, prestador, resena = await escenario(client, engine)
        client.put(
            f"{API}/resenas/{resena}",
            json={"puntuacion": 1},
            headers=como(turista, "Turista", '"1"'),
        )

        r = responder(client, resena, prestador, '"1"', "Gracias")

        assert (r.status_code, r.json()["error"]) == (409, "VERSION_DISTINTA")
        assert r.headers["ETag"] == '"2"'

    async def test_la_respuesta_sobrevive_a_la_edicion_del_turista(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista, prestador, resena = await escenario(client, engine)
        responder(client, resena, prestador, '"1"', "Gracias")

        r = client.put(
            f"{API}/resenas/{resena}",
            json={"puntuacion": 4},
            headers=como(turista, "Turista", '"2"'),
        )

        assert r.status_code == 200 and r.json()["respuesta"]["texto"] == "Gracias"

    def test_una_que_no_existe(self, client: TestClient) -> None:
        r = responder(client, str(uuid4()), uuid4(), '"1"', "Hola")
        assert (r.status_code, r.json()["error"]) == (404, "NO_ENCONTRADO")

    @pytest.mark.parametrize("texto", ["", "   ", "x" * 1001])
    async def test_texto_invalido(
        self, client: TestClient, engine: AsyncEngine, texto: str
    ) -> None:
        _, prestador, resena = await escenario(client, engine)
        r = responder(client, resena, prestador, '"1"', texto)
        assert (r.status_code, r.json()["error"]) == (400, "VALIDACION")
