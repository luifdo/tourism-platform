"""Paso 5.3a: patrón outbox. Los eventos quedan en evento_outbox en la misma transacción que el cambio."""

import json
from pathlib import Path
from uuid import UUID, uuid4

from jsonschema import Draft202012Validator
from sqlalchemy import select

from domain.eventos import EventoDominio
from infrastructure.http import demo
from infrastructure.persistence.db import fabrica_sesiones
from infrastructure.persistence.postgres import UnidadDeTrabajoPostgres
from infrastructure.persistence.tablas import evento_outbox

BASE = "/api/bookings"
EVENTOS = Path(__file__).resolve().parents[4] / "contracts" / "events"
TURISTA = {"X-Usuario-Id": str(demo.USUARIO_TURISTA_DEMO), "X-Usuario-Rol": "Turista"}
PRESTADOR = {"X-Usuario-Id": str(demo.USUARIO_PRESTADOR_DEMO), "X-Usuario-Rol": "Prestador"}


def validar_contra_contrato(sobre: dict) -> None:
    """El sobre contra envelope.v1.json y su payload contra <event_type>.v<version>.json."""
    esquema = lambda nombre: json.loads((EVENTOS / nombre).read_text(encoding="utf-8"))  # noqa: E731
    Draft202012Validator(esquema("envelope.v1.json"), format_checker=Draft202012Validator.FORMAT_CHECKER).validate(sobre)
    Draft202012Validator(
        esquema(f"{sobre['event_type']}.v{sobre['version']}.json"), format_checker=Draft202012Validator.FORMAT_CHECKER
    ).validate(sobre["payload"])


async def solicitar(cliente, personas=2, **extra_headers):
    return await cliente.post(
        BASE,
        json={"servicio_id": str(demo.SERVICIO_DEMO), "fecha_reserva": "2026-11-10", "numero_personas": personas},
        headers={**TURISTA, **extra_headers},
    )


async def test_solicitar_deja_sus_eventos_pendientes_y_en_orden(cliente, motor):
    r = await solicitar(cliente, **{"X-Correlation-ID": "corr-outbox"})
    assert r.status_code == 201
    async with motor.connect() as con:
        filas = (await con.execute(select(evento_outbox).order_by(evento_outbox.c.creado_en))).mappings().all()

    assert [f["tipo"] for f in filas] == ["reserva.solicitada", "auditoria.registrada", "disponibilidad.actualizada"]
    for f in filas:
        assert f["id"] == UUID(f["sobre"]["event_id"])  # el id de la fila es el event_id: deduplica
        assert f["tipo"] == f["sobre"]["event_type"]
        assert (f["publicado_en"], f["intentos"], f["ultimo_error"]) == (None, 0, None)  # pendiente
        assert f["sobre"]["correlation_id"] == "corr-outbox"
    assert len({f["creado_en"] for f in filas}) == 3  # clock_timestamp: cada uno con su instante
    assert filas[0]["sobre"]["payload"]["reserva_id"] == r.json()["id"]


async def test_todos_los_eventos_del_ciclo_cumplen_el_contrato(cliente, outbox):
    reserva = (await solicitar(cliente)).json()
    await cliente.patch(f"{BASE}/{reserva['id']}", json={"numero_personas": 3}, headers={**TURISTA, "If-Match": '"1"'})
    await cliente.post(f"{BASE}/{reserva['id']}/confirmar", headers=PRESTADOR)
    await cliente.post(f"{BASE}/{reserva['id']}/cancelar", json={"motivo": "Cambio de planes"}, headers=TURISTA)
    otra = (await cliente.post(
        BASE, json={"servicio_id": str(demo.SERVICIO_DEMO), "fecha_reserva": "2026-11-11", "numero_personas": 1},
        headers=TURISTA,
    )).json()
    await cliente.post(f"{BASE}/{otra['id']}/rechazar", json={"motivo": "Sin guía ese día"}, headers=PRESTADOR)

    sobres = await outbox()
    tipos = {s["event_type"] for s in sobres}
    assert {"reserva.solicitada", "reserva.modificada", "reserva.confirmada", "reserva.cancelada",
            "reserva.rechazada", "auditoria.registrada", "disponibilidad.actualizada"} <= tipos
    for sobre in sobres:
        validar_contra_contrato(sobre)


async def test_un_rechazo_de_negocio_no_deja_eventos(cliente, outbox):
    assert (await solicitar(cliente, personas=11)).status_code == 409
    assert await outbox() == []


async def test_un_acceso_denegado_queda_en_el_outbox(cliente, outbox):
    """ESC-04: el prestador intenta solicitar una reserva (solo turistas)."""
    r = await cliente.post(
        BASE, json={"servicio_id": str(demo.SERVICIO_DEMO), "fecha_reserva": "2026-11-10", "numero_personas": 1},
        headers=PRESTADOR,
    )
    assert r.status_code == 403
    [sobre] = await outbox()
    validar_contra_contrato(sobre)
    assert sobre["payload"]["accion"] == "ACCESS_DENIED" and sobre["payload"]["resultado"] == "DENEGADO"


async def test_sin_commit_no_queda_ningun_evento(motor, outbox):
    async with UnidadDeTrabajoPostgres(fabrica_sesiones(motor)) as uow:
        await uow.outbox.agregar([EventoDominio("auditoria.registrada", {"usuario_id": str(uuid4())})], None)
    assert await outbox() == []
