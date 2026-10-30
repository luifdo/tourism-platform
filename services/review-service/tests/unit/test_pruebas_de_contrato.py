"""Los validadores de contrato (tests/conftest.py) detectan errores de verdad, y los eventos
que publica el servicio, armados por el outbox real, cumplen contracts/events/.

Sin estas pruebas, un validador mal conectado dejaría pasar todo sin que nadie lo note.
"""

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.entities.elegibilidad_resena import ElegibilidadResena
from app.domain.entities.resena import Resena
from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.domain.events.evento_dominio import EventoDominio
from app.domain.events.resena_ocultada import ResenaOcultada
from app.domain.value_objects.contenido_resena import ContenidoResena
from app.domain.value_objects.resultado_auditoria import ResultadoAuditoria
from app.infrastructure.persistence.repositorios.outbox import SqlOutbox

AHORA = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)


class SesionQueGuarda:
    def __init__(self) -> None:
        self.agregados: list[Any] = []

    def add(self, modelo: Any) -> None:
        self.agregados.append(modelo)


async def sobre_del_outbox(evento: EventoDominio) -> dict[str, Any]:
    sesion = SesionQueGuarda()
    await SqlOutbox(sesion).agregar(evento)  # type: ignore[arg-type]
    [modelo] = sesion.agregados
    return modelo.sobre


def publicada() -> EventoDominio:
    turista, servicio = uuid4(), uuid4()
    elegible = ElegibilidadResena(
        turista_id=turista, servicio_id=servicio, ultima_visita=date(2026, 11, 14)
    )
    _, evento = Resena.escribir(turista, servicio, elegible, ContenidoResena(4), AHORA)
    return evento


EVENTOS_PUBLICADOS = {
    "resena.publicada": publicada,
    "resena.ocultada": lambda: ResenaOcultada(
        resena_id=uuid4(),
        servicio_id=uuid4(),
        turista_id=uuid4(),
        puntuacion=2,
        moderada_por=uuid4(),
        motivo="Datos personales",
        ocurrido_en=AHORA,
    ),
    "ACCESS_DENIED": lambda: AuditoriaRegistrada(
        usuario_id=uuid4(),
        accion="ACCESS_DENIED",
        resultado=ResultadoAuditoria.DENEGADO,
        detalles={"motivo": "NO_ELEGIBLE", "rol": "Turista", "servicio_id": str(uuid4())},
        ip_origen="190.0.0.1",
        ocurrido_en=AHORA,
    ),
    "MODERACION": lambda: AuditoriaRegistrada(
        usuario_id=uuid4(),
        accion="MODERACION",
        detalles={"decision": "OCULTAR", "estado_anterior": "EN_REVISION"},
        ip_origen="181.0.0.9",
        ocurrido_en=AHORA,
    ),
}


@pytest.mark.parametrize("nombre", EVENTOS_PUBLICADOS)
async def test_cada_evento_que_publicamos_cumple_su_esquema(
    nombre: str, validar_evento: Any
) -> None:
    validar_evento(await sobre_del_outbox(EVENTOS_PUBLICADOS[nombre]()))


class TestElValidadorDeEventosDetectaErrores:
    async def test_payload_que_no_cumple(self, validar_evento: Any) -> None:
        sobre = await sobre_del_outbox(EVENTOS_PUBLICADOS["resena.publicada"]())
        sobre["payload"]["puntuacion"] = 6
        with pytest.raises(AssertionError, match="payload.puntuacion"):
            validar_evento(sobre)

    async def test_sobre_con_campos_de_mas(self, validar_evento: Any) -> None:
        sobre = await sobre_del_outbox(EVENTOS_PUBLICADOS["MODERACION"]())
        sobre["otro"] = 1
        with pytest.raises(AssertionError, match="sobre"):
            validar_evento(sobre)

    async def test_evento_sin_esquema(self, validar_evento: Any) -> None:
        sobre = await sobre_del_outbox(EVENTOS_PUBLICADOS["MODERACION"]())
        sobre["version"] = 9
        with pytest.raises(AssertionError, match="No hay esquema"):
            validar_evento(sobre)


def app_que_incumple() -> FastAPI:
    app = FastAPI()

    @app.get("/api/reviews/servicios/{servicio_id}/resumen")
    def resumen(servicio_id: str) -> dict[str, Any]:
        return {"total": "muchas"}  # tipo equivocado y le faltan campos

    @app.delete("/api/reviews/resenas/{resena_id}")
    def borrar(resena_id: str) -> dict[str, Any]:
        return {}

    return app


class TestElValidadorRestDetectaErrores:
    def test_cuerpo_que_no_cumple_el_esquema(self) -> None:
        with (
            TestClient(app_que_incumple()) as c,
            pytest.raises(AssertionError, match="no cumple review.yaml"),
        ):
            c.get(f"/api/reviews/servicios/{uuid4()}/resumen")

    def test_operacion_que_no_esta_en_el_contrato(self) -> None:
        with (
            TestClient(app_que_incumple()) as c,
            pytest.raises(AssertionError, match="no cumple review.yaml"),
        ):
            c.delete(f"/api/reviews/resenas/{uuid4()}")  # el contrato no tiene DELETE

    @pytest.mark.sin_contrato
    def test_con_la_marca_no_se_valida(self) -> None:
        with TestClient(app_que_incumple()) as c:
            assert c.get(f"/api/reviews/servicios/{uuid4()}/resumen").status_code == 200
