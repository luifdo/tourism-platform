"""El sobre que guarda el outbox cumple `contracts/events/` del monorepo (C-17)."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from app.domain.events.prestador_suspendido import PrestadorSuspendido
from app.infrastructure.observabilidad.contexto_correlacion import fijar_correlation_id
from app.infrastructure.persistence.models import Outbox
from app.infrastructure.persistence.outbox_repository import SqlAlchemyOutbox
from tests.fakes import AHORA

# tests/unit/ -> tests/ -> iam-service/ -> services/ -> raíz del monorepo
CONTRATOS = Path(__file__).resolve().parents[4] / "contracts" / "events"


class SesionQueGuarda:
    """Lo mínimo de AsyncSession que usa SqlAlchemyOutbox."""

    def __init__(self) -> None:
        self.agregados: list[Any] = []

    def add(self, objeto: Any) -> None:
        self.agregados.append(objeto)

    async def flush(self) -> None:
        pass


def validador(nombre: str) -> Draft202012Validator:
    esquema = json.loads((CONTRATOS / nombre).read_text(encoding="utf-8"))
    return Draft202012Validator(esquema, format_checker=Draft202012Validator.FORMAT_CHECKER)


async def guardar(evento: PrestadorSuspendido) -> Outbox:
    sesion = SesionQueGuarda()
    await SqlAlchemyOutbox(sesion).agregar(evento)  # type: ignore[arg-type]
    [fila] = sesion.agregados
    return fila


@pytest.fixture
def evento() -> PrestadorSuspendido:
    return PrestadorSuspendido(
        ocurrido_en=AHORA, usuario_id=uuid.uuid4(), suspendido_por=uuid.uuid4()
    )


async def test_sobre_y_payload_cumplen_el_contrato(evento: PrestadorSuspendido) -> None:
    fijar_correlation_id("corr-admin-1")

    fila = await guardar(evento)

    sobre = fila.sobre
    validador("envelope.v1.json").validate(sobre)
    validador("prestador.suspendido.v1.json").validate(sobre["payload"])
    assert (sobre["event_type"], sobre["version"], sobre["producer"]) == (
        "prestador.suspendido",
        1,
        "iam-service",
    )
    assert datetime.fromisoformat(sobre["occurred_at"]) == AHORA
    assert sobre["correlation_id"] == "corr-admin-1"
    assert uuid.UUID(sobre["event_id"]) == fila.event_id
    assert (fila.event_type, fila.creado_en, fila.intentos) == ("prestador.suspendido", AHORA, 0)
    # prestador_id = usuario_id (C-08) y sin motivo (C-41).
    assert sobre["payload"]["prestador_id"] == sobre["payload"]["usuario_id"]
    assert "motivo" not in sobre["payload"]


async def test_sin_correlation_id_no_lleva_la_clave(evento: PrestadorSuspendido) -> None:
    fijar_correlation_id(None)

    sobre = (await guardar(evento)).sobre

    assert "correlation_id" not in sobre
    validador("envelope.v1.json").validate(sobre)


def test_el_validador_rechaza_un_payload_fuera_del_contrato() -> None:
    # Comprueba que la prueba de arriba de verdad valida (formato uuid y claves requeridas).
    malo = {"prestador_id": "no-es-uuid", "usuario_id": str(uuid.uuid4())}

    errores = list(validador("prestador.suspendido.v1.json").iter_errors(malo))

    assert {e.validator for e in errores} == {"format", "required"}
