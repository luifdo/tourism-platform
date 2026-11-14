"""Lecturas de punta a punta (paso 7): públicas, del turista y del prestador.

Cada respuesta se valida contra review.yaml (tests/conftest.py).
"""

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.main import create_app

API = "/api/reviews"
INICIO = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def client(database_url: str, engine: AsyncEngine) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(database_url=database_url))) as c:
        yield c


def como(usuario: UUID, rol: str) -> dict[str, str]:
    return {"X-Usuario-Id": str(usuario), "X-Usuario-Rol": rol}


async def resena(
    engine: AsyncEngine,
    servicio: UUID,
    puntuacion: int,
    *,
    estado: str = "PUBLICADA",
    dias: int = 0,
    turista: UUID | None = None,
    aspectos: dict[str, int] | None = None,
    respondida: bool = False,
) -> UUID:
    """Inserta una reseña creada `dias` después de INICIO."""
    resena_id = uuid4()
    respuesta = (
        json.dumps({"texto": "Gracias", "respondida_en": INICIO.isoformat()})
        if respondida
        else None
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO resena (id, servicio_id, turista_id, puntuacion, aspectos, respuesta,"
                " ultima_visita, estado, creada_en)"
                " VALUES (:id, :s, :t, :p, CAST(:a AS jsonb), CAST(:r AS jsonb), :v, :e, :c)"
            ),
            {
                "id": resena_id,
                "s": servicio,
                "t": turista or uuid4(),
                "p": puntuacion,
                "a": json.dumps(aspectos or {}),
                "r": respuesta,
                "v": date(2026, 10, 20),
                "e": estado,
                "c": INICIO + timedelta(days=dias),
            },
        )
    return resena_id


async def ejecutar(engine: AsyncEngine, sql: str, **datos: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), datos)


class TestPublicas:
    async def test_lista_solo_las_publicadas_en_los_tres_ordenes(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        servicio = uuid4()
        vieja_buena = await resena(engine, servicio, 5, dias=0)
        nueva_mala = await resena(engine, servicio, 1, dias=2)
        media = await resena(engine, servicio, 3, dias=1)
        await resena(engine, servicio, 4, dias=3, estado="EN_REVISION")
        await resena(engine, servicio, 2, dias=4, estado="OCULTA")
        await resena(engine, uuid4(), 5)  # de otro servicio

        def ids(orden: str) -> list[str]:
            r = client.get(f"{API}/servicios/{servicio}/resenas", params={"orden": orden})
            assert r.status_code == 200 and r.json()["total"] == 3
            return [i["id"] for i in r.json()["items"]]

        assert ids("recientes") == [str(nueva_mala), str(media), str(vieja_buena)]
        assert ids("mejores") == [str(vieja_buena), str(media), str(nueva_mala)]
        assert ids("peores") == [str(nueva_mala), str(media), str(vieja_buena)]

    async def test_pagina(self, client: TestClient, engine: AsyncEngine) -> None:
        servicio = uuid4()
        for dia in range(5):
            await resena(engine, servicio, 4, dias=dia)
        url = f"{API}/servicios/{servicio}/resenas"

        segunda = client.get(url, params={"pagina": 2, "tamano": 2}).json()
        fuera = client.get(url, params={"pagina": 9, "tamano": 2}).json()

        assert (len(segunda["items"]), segunda["total"], segunda["pagina"]) == (2, 5, 2)
        assert (fuera["items"], fuera["total"]) == ([], 5)

    async def test_resumen_cuenta_publicadas_y_en_revision(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        servicio = uuid4()
        await resena(engine, servicio, 5, aspectos={"LIMPIEZA": 5, "ATENCION": 4})
        await resena(engine, servicio, 4, aspectos={"LIMPIEZA": 4})
        await resena(engine, servicio, 2, estado="EN_REVISION", aspectos={"LIMPIEZA": 3})
        await resena(engine, servicio, 1, estado="OCULTA", aspectos={"LIMPIEZA": 1})

        r = client.get(f"{API}/servicios/{servicio}/resumen")

        assert r.status_code == 200
        assert r.json() == {
            "servicio_id": str(servicio),
            "total": 3,
            "promedio": 3.67,
            "distribucion": {"1": 0, "2": 1, "3": 0, "4": 1, "5": 1},
            "aspectos": {
                "LIMPIEZA": {"promedio": 4.0, "total": 3},
                "ATENCION": {"promedio": 4.0, "total": 1},
            },
        }

    def test_resumen_sin_resenas(self, client: TestClient) -> None:
        servicio = uuid4()
        r = client.get(f"{API}/servicios/{servicio}/resumen")
        assert r.json() == {
            "servicio_id": str(servicio),
            "total": 0,
            "promedio": None,
            "distribucion": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
            "aspectos": {},
        }

    async def test_una_resena_solo_si_esta_publicada(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        servicio = uuid4()
        publicada = await resena(engine, servicio, 4)
        oculta = await resena(engine, servicio, 4, estado="OCULTA")

        r = client.get(f"{API}/resenas/{publicada}", headers={"Accept-Language": "en"})
        assert r.status_code == 200 and r.json()["autor"] == "Verified tourist"
        assert "turista_id" not in r.json() and "estado" not in r.json()
        for ausente in (oculta, uuid4()):
            assert client.get(f"{API}/resenas/{ausente}").status_code == 404

    @pytest.mark.parametrize("params", [{"orden": "aleatorio"}, {"tamano": 51}, {"pagina": 0}])
    def test_parametros_invalidos(self, client: TestClient, params: dict[str, Any]) -> None:
        r = client.get(f"{API}/servicios/{uuid4()}/resenas", params=params)
        assert (r.status_code, r.json()["error"]) == (400, "VALIDACION")


class TestTurista:
    async def test_mis_resenas_en_todos_los_estados(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista = uuid4()
        await resena(engine, uuid4(), 4, turista=turista, dias=0)
        await resena(engine, uuid4(), 2, turista=turista, dias=1, estado="OCULTA")
        await resena(engine, uuid4(), 5)  # de otro turista

        r = client.get(f"{API}/turista/resenas", headers=como(turista, "Turista"))

        assert r.status_code == 200 and r.json()["total"] == 2
        assert [(i["estado"], i["estado_etiqueta"]) for i in r.json()["items"]] == [
            ("OCULTA", "Oculta"),
            ("PUBLICADA", "Publicada"),
        ]

    async def test_pendientes_sin_los_ya_resenados(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        turista, resenado, reciente, viejo = uuid4(), uuid4(), uuid4(), uuid4()
        for servicio, visita in (
            (resenado, date(2026, 11, 1)),
            (reciente, date(2026, 11, 10)),
            (viejo, date(2026, 9, 5)),
        ):
            await ejecutar(
                engine,
                "INSERT INTO elegibilidad_resena VALUES (:t, :s, :v)",
                t=turista,
                s=servicio,
                v=visita,
            )
        await resena(engine, resenado, 4, turista=turista)

        r = client.get(f"{API}/turista/pendientes", headers=como(turista, "Turista"))

        assert r.json() == [
            {"servicio_id": str(reciente), "ultima_visita": "2026-11-10"},
            {"servicio_id": str(viejo), "ultima_visita": "2026-09-05"},
        ]

    def test_otro_rol_no_ve_pendientes(self, client: TestClient) -> None:
        r = client.get(f"{API}/turista/pendientes", headers=como(uuid4(), "Prestador"))
        assert (r.status_code, r.json()["error"]) == (403, "ROL_NO_PERMITIDO")


class TestPrestador:
    async def preparar(self, engine: AsyncEngine) -> tuple[UUID, UUID, UUID]:
        prestador, propio, otro = uuid4(), uuid4(), uuid4()
        for servicio, dueno in ((propio, prestador), (otro, uuid4())):
            await ejecutar(
                engine,
                "INSERT INTO servicio_dueno VALUES (:s, :d, 1)",
                s=servicio,
                d=dueno,
            )
        return prestador, propio, otro

    async def test_ve_las_de_sus_servicios_publicadas_y_en_revision(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        prestador, propio, otro = await self.preparar(engine)
        await resena(engine, propio, 5, dias=0, respondida=True)
        await resena(engine, propio, 2, dias=1, estado="EN_REVISION")
        await resena(engine, propio, 1, dias=2, estado="OCULTA")
        await resena(engine, otro, 4)

        r = client.get(f"{API}/prestador/resenas", headers=como(prestador, "Prestador"))
        sin_responder = client.get(
            f"{API}/prestador/resenas",
            params={"sin_respuesta": "true", "servicio_id": str(propio)},
            headers=como(prestador, "Prestador"),
        )

        assert r.status_code == 200
        assert [(i["estado"], i["version"]) for i in r.json()["items"]] == [
            ("EN_REVISION", 1),
            ("PUBLICADA", 1),
        ]
        assert r.json()["items"][1]["respuesta"]["texto"] == "Gracias"
        assert [i["estado"] for i in sin_responder.json()["items"]] == ["EN_REVISION"]

    async def test_un_servicio_ajeno(self, client: TestClient, engine: AsyncEngine) -> None:
        prestador, _, otro = await self.preparar(engine)
        r = client.get(
            f"{API}/prestador/resenas",
            params={"servicio_id": str(otro)},
            headers=como(prestador, "Prestador"),
        )
        assert (r.status_code, r.json()["error"]) == (403, "NO_ES_DUENO")

    async def test_un_turista_no_puede_y_se_audita(
        self, client: TestClient, engine: AsyncEngine
    ) -> None:
        r = client.get(f"{API}/prestador/resenas", headers=como(uuid4(), "Turista"))
        assert (r.status_code, r.json()["error"]) == (403, "ROL_NO_PERMITIDO")
        async with engine.connect() as conn:
            auditados = await conn.scalar(
                text("SELECT count(*) FROM outbox WHERE event_type = 'auditoria.registrada'")
            )
        assert auditados == 1
