"""Los validadores de contrato (tests/conftest.py) detectan errores de verdad, y los eventos
que publica el servicio, armados por el outbox real, cumplen contracts/events/.

Sin estas pruebas, un validador mal conectado dejaría pasar todo sin que nadie lo note.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.domain.events.evento_dominio import EventoDominio
from app.domain.events.servicio_publicado import ServicioPublicado
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.catalogos import ResultadoAuditoria, UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.persistence.repositorios.outbox import SqlOutbox

AHORA = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)


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


def servicio() -> AtractivoServicio:
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Sierra Viva")
    datos = DatosServicio(
        nombre=TextoTraducido(es="Pozo Azul"),
        descripcion=TextoTraducido(es="Entrada"),
        tipo=TipoServicio.RESERVA_PARQUE,
        unidad_tarifa=UnidadTarifa.POR_PERSONA,
        atributos=AtributosServicio(entrada=BloqueEntrada()),
        ubicacion=Coordenada(lat=11.14, lon=-74.11),
        tarifa_base=Tarifa(Decimal("10000")),
        capacidad_aforo_diario=20,
    )
    return AtractivoServicio.registrar(perfil, datos, "https://s3/", AHORA)


EVENTOS_PUBLICADOS = {
    "servicio.publicado": lambda: ServicioPublicado.de(servicio(), AHORA),
    "ACCESS_DENIED": lambda: AuditoriaRegistrada(
        usuario_id=uuid4(),
        accion="ACCESS_DENIED",
        resultado=ResultadoAuditoria.DENEGADO,
        detalles={"ruta": "/api/catalog/zonas", "metodo": "POST", "rol": "Turista"},
        ip_origen="190.0.0.1",
        ocurrido_en=AHORA,
    ),
    "ZONA_CREADA": lambda: AuditoriaRegistrada(
        usuario_id=uuid4(),
        accion="ZONA_CREADA",
        detalles={"zona_id": str(uuid4())},
        ocurrido_en=AHORA,
    ),
    "EXPORT": lambda: AuditoriaRegistrada(
        usuario_id=uuid4(),
        accion="EXPORT",
        detalles={"reporte": "demanda", "formato": "csv", "zona": None},
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
        sobre = await sobre_del_outbox(EVENTOS_PUBLICADOS["servicio.publicado"]())
        sobre["payload"]["capacidad_aforo_diario"] = "veinte"
        with pytest.raises(AssertionError, match="payload.capacidad_aforo_diario"):
            validar_evento(sobre)

    async def test_sobre_con_campos_de_mas(self, validar_evento: Any) -> None:
        sobre = await sobre_del_outbox(EVENTOS_PUBLICADOS["EXPORT"]())
        sobre["otro"] = 1
        with pytest.raises(AssertionError, match="sobre"):
            validar_evento(sobre)

    async def test_evento_sin_esquema(self, validar_evento: Any) -> None:
        sobre = await sobre_del_outbox(EVENTOS_PUBLICADOS["EXPORT"]())
        sobre["version"] = 9
        with pytest.raises(AssertionError, match="No hay esquema"):
            validar_evento(sobre)


def app_que_incumple() -> FastAPI:
    app = FastAPI()

    @app.get("/api/catalog/zonas")
    def zonas() -> list[dict[str, Any]]:
        return [{"codigo": "minca"}]  # le faltan id, nombre y centro

    @app.get("/api/catalog/zonas/{zona_id}")
    def zona(zona_id: str) -> dict[str, Any]:
        return {}

    return app


class TestElValidadorRestDetectaErrores:
    def test_cuerpo_que_no_cumple_el_esquema(self) -> None:
        with (
            TestClient(app_que_incumple()) as c,
            pytest.raises(AssertionError, match="no cumple catalog.yaml"),
        ):
            c.get("/api/catalog/zonas")

    def test_operacion_que_no_esta_en_el_contrato(self) -> None:
        with (
            TestClient(app_que_incumple()) as c,
            pytest.raises(AssertionError, match="no cumple catalog.yaml"),
        ):
            c.post("/api/catalog/zonas/x")  # el contrato no tiene POST /zonas/{zona_id}

    @pytest.mark.sin_contrato
    def test_con_la_marca_no_se_valida(self) -> None:
        with TestClient(app_que_incumple()) as c:
            assert c.get("/api/catalog/zonas").status_code == 200
