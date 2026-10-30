"""UC15 de punta a punta: la API con PostgreSQL real.

Cada respuesta se valida contra review.yaml (tests/conftest.py) y cada evento que queda en
el outbox, contra contracts/events/ (fixture `engine`).
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

RESENAS = "/api/reviews/resenas"


@pytest.fixture
def client(database_url: str, engine: AsyncEngine) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(database_url=database_url))) as c:
        yield c


def como(usuario: UUID, rol: str = "Turista", **extra: str) -> dict[str, str]:
    return {"X-Usuario-Id": str(usuario), "X-Usuario-Rol": rol, **extra}


async def elegible(engine: AsyncEngine, turista: UUID, servicio: UUID) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO elegibilidad_resena (turista_id, servicio_id, ultima_visita)"
                " VALUES (:t, :s, :f)"
            ),
            {"t": turista, "s": servicio, "f": date(2026, 11, 14)},
        )


async def eventos(engine: AsyncEngine, tipo: str) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        filas = await conn.execute(
            text("SELECT sobre FROM outbox WHERE event_type = :t ORDER BY creado_en"), {"t": tipo}
        )
        return [sobre for (sobre,) in filas]


def cuerpo(servicio: UUID, **cambios: Any) -> dict[str, Any]:
    return {
        "servicio_id": str(servicio),
        "puntuacion": 4,
        "aspectos": {"LIMPIEZA": 5, "GUIANZA": 3},
        "comentario": "Muy buena <b>guianza</b>, precio < 50 mil",
    } | cambios


async def escrita(client: TestClient, engine: AsyncEngine) -> tuple[UUID, dict[str, Any]]:
    turista, servicio = uuid4(), uuid4()
    await elegible(engine, turista, servicio)
    r = client.post(RESENAS, json=cuerpo(servicio), headers=como(turista))
    assert r.status_code == 201, r.text
    return turista, r.json()


class TestEscribir:
    async def test_publica_la_resena_anonima_y_su_evento(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista, servicio = uuid4(), uuid4()
        await elegible(engine, turista, servicio)

        r = client.post(RESENAS, json=cuerpo(servicio), headers=como(turista))

        assert r.status_code == 201
        assert r.headers["ETag"] == '"1"'
        datos = r.json()
        assert datos["autor"] == "Turista verificado"
        assert str(turista) not in r.text  # anónima
        assert datos["mes_visita"] == "2026-11"
        assert datos["estado"] == "PUBLICADA" and datos["estado_etiqueta"] == "Publicada"
        assert datos["aspectos"] == {"LIMPIEZA": 5, "GUIANZA": 3}
        assert datos["aspectos_etiquetas"] == {"LIMPIEZA": "Limpieza", "GUIANZA": "Guianza"}
        # El comentario se guarda tal cual: la PWA lo muestra como texto.
        assert datos["comentario"] == "Muy buena <b>guianza</b>, precio < 50 mil"
        [evento] = await eventos(engine, "resena.publicada")
        assert evento["payload"] == {
            "resena_id": datos["id"],
            "servicio_id": str(servicio),
            "turista_id": str(turista),
            "puntuacion": 4,
        }

    async def test_etiquetas_en_ingles(self, client: TestClient, engine: AsyncEngine) -> None:
        turista, servicio = uuid4(), uuid4()
        await elegible(engine, turista, servicio)

        r = client.post(
            RESENAS, json=cuerpo(servicio), headers=como(turista, **{"Accept-Language": "en"})
        )

        assert r.headers["Content-Language"] == "en"
        assert r.json()["autor"] == "Verified tourist"
        assert r.json()["aspectos_etiquetas"]["LIMPIEZA"] == "Cleanliness"

    async def test_sin_reserva_finalizada_no_es_elegible_y_se_audita(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista, servicio = uuid4(), uuid4()

        r = client.post(
            RESENAS,
            json=cuerpo(servicio),
            headers=como(turista, **{"X-Forwarded-For": "190.0.0.7, 10.0.0.1"}),
        )

        assert (r.status_code, r.json()["error"]) == (403, "NO_ELEGIBLE")
        [auditoria] = await eventos(engine, "auditoria.registrada")
        assert auditoria["payload"]["accion"] == "ACCESS_DENIED"
        assert auditoria["payload"]["usuario_id"] == str(turista)
        assert auditoria["payload"]["ip_origen"] == "190.0.0.7"
        assert auditoria["payload"]["detalles"]["motivo"] == "NO_ELEGIBLE"
        assert auditoria["payload"]["detalles"]["servicio_id"] == str(servicio)
        assert await eventos(engine, "resena.publicada") == []

    async def test_otro_rol_no_puede_y_se_audita(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        r = client.post(RESENAS, json=cuerpo(uuid4()), headers=como(uuid4(), "Prestador"))

        assert (r.status_code, r.json()["error"]) == (403, "ROL_NO_PERMITIDO")
        [auditoria] = await eventos(engine, "auditoria.registrada")
        assert auditoria["payload"]["detalles"]["roles_permitidos"] == ["Turista"]

    async def test_una_por_turista_y_servicio(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista, servicio = uuid4(), uuid4()
        await elegible(engine, turista, servicio)
        client.post(RESENAS, json=cuerpo(servicio), headers=como(turista))

        r = client.post(RESENAS, json=cuerpo(servicio), headers=como(turista))

        assert (r.status_code, r.json()["error"]) == (409, "YA_RESENADO")

    async def test_el_reenvio_con_la_misma_clave_no_repite(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista, servicio = uuid4(), uuid4()
        await elegible(engine, turista, servicio)
        cabeceras = como(turista, **{"Idempotency-Key": str(uuid4())})

        primera = client.post(RESENAS, json=cuerpo(servicio), headers=cabeceras)
        repetida = client.post(RESENAS, json=cuerpo(servicio), headers=cabeceras)

        assert repetida.status_code == 201
        assert repetida.headers["Idempotent-Replayed"] == "true"
        assert repetida.json() == primera.json()
        assert len(await eventos(engine, "resena.publicada")) == 1

    @pytest.mark.parametrize(
        "cambios",
        [
            {"puntuacion": 6},
            {"puntuacion": "5"},
            {"aspectos": {"WIFI": 4}},
            {"aspectos": {"LIMPIEZA": 0}},
            {"comentario": "x" * 2001},
            {"extra": True},
        ],
    )
    async def test_datos_invalidos(
        self, client: TestClient, engine: AsyncEngine, cambios: dict[str, Any]
    ) -> None:
        r = client.post(RESENAS, json=cuerpo(uuid4(), **cambios), headers=como(uuid4()))
        assert (r.status_code, r.json()["error"]) == (400, "VALIDACION")

    def test_sin_identidad(self, client: TestClient) -> None:
        r = client.post(RESENAS, json=cuerpo(uuid4()))
        assert (r.status_code, r.json()["error"]) == (401, "NO_AUTENTICADO")


class TestEditar:
    async def test_edita_con_la_version_y_publica_la_nueva_nota(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista, resena = await escrita(client, engine)

        r = client.put(
            f"{RESENAS}/{resena['id']}",
            json={"puntuacion": 2, "comentario": "Cambió mucho"},
            headers=como(turista, **{"If-Match": '"1"'}),
        )

        assert r.status_code == 200
        assert r.headers["ETag"] == '"2"'
        assert r.json()["puntuacion"] == 2 and r.json()["aspectos"] == {}
        assert r.json()["editada_en"] is not None
        notas = [e["payload"]["puntuacion"] for e in await eventos(engine, "resena.publicada")]
        assert notas == [4, 2]

    async def test_sin_if_match(self, client: TestClient, engine: AsyncEngine) -> None:
        turista, resena = await escrita(client, engine)
        r = client.put(f"{RESENAS}/{resena['id']}", json={"puntuacion": 2}, headers=como(turista))
        assert (r.status_code, r.json()["error"]) == (428, "FALTA_IF_MATCH")

    async def test_con_version_vieja_devuelve_la_actual(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista, resena = await escrita(client, engine)
        url = f"{RESENAS}/{resena['id']}"
        client.put(url, json={"puntuacion": 3}, headers=como(turista, **{"If-Match": "1"}))

        r = client.put(url, json={"puntuacion": 2}, headers=como(turista, **{"If-Match": "1"}))

        assert (r.status_code, r.json()["error"]) == (409, "VERSION_DISTINTA")
        assert r.headers["ETag"] == '"2"'

    async def test_solo_el_autor(self, client: TestClient, engine: AsyncEngine) -> None:
        _, resena = await escrita(client, engine)
        r = client.put(
            f"{RESENAS}/{resena['id']}",
            json={"puntuacion": 1},
            headers=como(uuid4(), **{"If-Match": '"1"'}),
        )
        assert (r.status_code, r.json()["error"]) == (403, "NO_ES_DUENO")

    async def test_en_revision_no_se_edita(self, client: TestClient, engine: AsyncEngine) -> None:
        turista, resena = await escrita(client, engine)
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE resena SET estado = 'EN_REVISION', version = 2 WHERE id = :id"),
                {"id": resena["id"]},
            )

        r = client.put(
            f"{RESENAS}/{resena['id']}",
            json={"puntuacion": 5},
            headers=como(turista, **{"If-Match": '"2"'}),
        )

        assert (r.status_code, r.json()["error"]) == (409, "RESENA_EN_MODERACION")

    def test_una_que_no_existe(self, client: TestClient) -> None:
        r = client.put(
            f"{RESENAS}/{uuid4()}",
            json={"puntuacion": 5},
            headers=como(uuid4(), **{"If-Match": '"1"'}),
        )
        assert (r.status_code, r.json()["error"]) == (404, "NO_ENCONTRADO")
