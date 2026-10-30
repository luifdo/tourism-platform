"""UC33 por HTTP: GET /api/iam/admin/bitacora (RNF-10, C-43)."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import ResultadoAuditoria, Rol
from app.domain.value_objects.filtro_bitacora import EntradaBitacora, FiltroBitacora
from app.domain.value_objects.token import TokenEmitido
from tests.api.conftest import (
    CORRELATION_ID,
    IP_CLIENTE,
    TOKEN_INVALIDO,
    bearer,
    emitir,
    unico_denegado,
)
from tests.fakes import AHORA, FakeUnitOfWork, RegistroAuditoria

URL = "/api/iam/admin/bitacora"


def entrada(minutos: int, **cambios: object) -> EntradaBitacora:
    valores: dict[str, object] = {
        "id": uuid.uuid4(),
        "fecha": AHORA - timedelta(minutes=minutos),
        "usuario_id": uuid.uuid4(),
        "accion": "ROLE_CHANGE",
        "resultado": ResultadoAuditoria.EXITO,
        "servicio_origen": "iam-service",
        "ip_origen": "190.24.10.5",
        "detalles": {"antes": {"rol": "Turista"}, "despues": {"rol": "Entidad"}},
        "correlation_id": "corr-1",
        "event_id": None,
    }
    return EntradaBitacora(**{**valores, **cambios})  # type: ignore[arg-type]


@pytest.fixture
def emitido_admin(client: TestClient) -> tuple[TokenEmitido, Usuario]:
    return emitir(client, Rol.ADMIN)


@pytest.fixture
def admin(emitido_admin: tuple[TokenEmitido, Usuario]) -> dict[str, str]:
    return bearer(emitido_admin[0].access_token)


@pytest.fixture
def admin_id(emitido_admin: tuple[TokenEmitido, Usuario]) -> uuid.UUID:
    assert emitido_admin[1].id is not None
    return emitido_admin[1].id


def unica_consulta(uow: FakeUnitOfWork, admin_id: uuid.UUID) -> RegistroAuditoria:
    """La fila AUDIT_VIEW que deja cada consulta (C-43)."""
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("AUDIT_VIEW", ResultadoAuditoria.EXITO)
    assert (registro.usuario_id, registro.ip_origen) == (admin_id, IP_CLIENTE)
    assert registro.correlation_id == CORRELATION_ID
    return registro


def test_sin_token_401(client: TestClient, uow: FakeUnitOfWork) -> None:
    response = client.get(URL)

    assert response.status_code == 401
    assert response.json() == TOKEN_INVALIDO
    assert unico_denegado(uow).detalles["motivo"] == "sin_token"
    assert uow.auditoria.filtros == []


@pytest.mark.parametrize("rol", [Rol.TURISTA, Rol.PRESTADOR, Rol.ENTIDAD])
def test_otro_rol_403(client: TestClient, uow: FakeUnitOfWork, rol: Rol) -> None:
    emitido, u = emitir(client, rol)

    response = client.get(URL, headers=bearer(emitido.access_token))

    assert response.status_code == 403
    assert response.json() == {
        "detail": "No tiene permisos para realizar esta acción.",
        "code": "ROL_INSUFICIENTE",
        "correlation_id": CORRELATION_ID,
    }
    assert unico_denegado(uow).usuario_id == u.id
    assert uow.auditoria.filtros == []


def test_sin_filtros_200(
    client: TestClient, uow: FakeUnitOfWork, admin: dict[str, str], admin_id: uuid.UUID
) -> None:
    propia, ajena = (
        entrada(1),
        entrada(
            5,
            accion="ZONA_CREADA",
            servicio_origen="catalog-service",
            ip_origen=None,
            usuario_id=None,
            event_id=uuid.uuid4(),
        ),
    )
    uow.auditoria.entradas = [propia, ajena]

    response = client.get(URL, headers=admin)

    assert response.status_code == 200
    data = response.json()
    assert (data["total"], data["pagina"], data["tamano"]) == (2, 1, 20)
    assert [i["id"] for i in data["items"]] == [str(propia.id), str(ajena.id)]
    assert data["items"][0] == {
        "id": str(propia.id),
        "fecha": "2026-10-23T14:59:00Z",
        "usuario_id": str(propia.usuario_id),
        "accion": "ROLE_CHANGE",
        "resultado": "Exito",
        "servicio_origen": "iam-service",
        "ip_origen": "190.24.10.5",
        "detalles": {"antes": {"rol": "Turista"}, "despues": {"rol": "Entidad"}},
        "correlation_id": "corr-1",
        "event_id": None,
    }
    assert data["items"][1]["event_id"] == str(ajena.event_id)
    assert uow.auditoria.filtros == [FiltroBitacora()]
    # La consulta queda registrada, sin filtros y con la página por defecto.
    registro = unica_consulta(uow, admin_id)
    assert registro.detalles == {"filtros": {}, "pagina": 1, "tamano": 20}
    # Se escribe después de leer y en otra transacción: dos entradas, un commit.
    assert (uow.entradas, uow.commits) == (2, 1)


def test_filtros_y_paginacion_llegan_al_repositorio(
    client: TestClient, uow: FakeUnitOfWork, admin: dict[str, str], admin_id: uuid.UUID
) -> None:
    usuario_id = uuid.uuid4()
    uow.auditoria.entradas = [entrada(i) for i in range(5)]

    response = client.get(
        URL,
        params={
            "usuario_id": str(usuario_id),
            "accion": "ACCESS_DENIED",
            "resultado": "Denegado",
            "servicio_origen": "booking-service",
            "desde": "2026-10-01T00:00:00-05:00",
            "hasta": "2026-10-31T00:00:00Z",
            "pagina": 2,
            "tamano": 2,
        },
        headers=admin,
    )

    assert response.status_code == 200
    data = response.json()
    assert (data["total"], data["pagina"], data["tamano"], len(data["items"])) == (5, 2, 2, 2)
    [filtro] = uow.auditoria.filtros
    assert filtro == FiltroBitacora(
        usuario_id=usuario_id,
        accion="ACCESS_DENIED",
        resultado=ResultadoAuditoria.DENEGADO,
        servicio_origen="booking-service",
        desde=datetime(2026, 10, 1, 5, tzinfo=UTC),
        hasta=datetime(2026, 10, 31, tzinfo=UTC),
        pagina=2,
        tamano=2,
    )
    # Los filtros usados y la página, nunca los resultados.
    registro = unica_consulta(uow, admin_id)
    assert registro.detalles == {
        "filtros": {
            "usuario_id": str(usuario_id),
            "accion": "ACCESS_DENIED",
            "resultado": "Denegado",
            "servicio_origen": "booking-service",
            "desde": "2026-10-01T00:00:00-05:00",
            "hasta": "2026-10-31T00:00:00+00:00",
        },
        "pagina": 2,
        "tamano": 2,
    }
    assert "items" not in registro.detalles


def test_si_falla_el_registro_la_consulta_responde_200(
    client: TestClient,
    uow: FakeUnitOfWork,
    admin: dict[str, str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uow.auditoria.entradas = [entrada(1)]

    async def falla(**_: object) -> None:
        raise ConnectionRefusedError("PostgreSQL caído")

    monkeypatch.setattr(uow.auditoria, "registrar", falla)

    with caplog.at_level(logging.ERROR):
        response = client.get(URL, headers=admin)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert "No se pudo registrar AUDIT_VIEW: ConnectionRefusedError" in caplog.text
    assert uow.commits == 0


@pytest.mark.parametrize(
    ("params", "campo"),
    [
        ({"tamano": 101}, "tamano"),
        ({"tamano": 0}, "tamano"),
        ({"pagina": 0}, "pagina"),
        ({"resultado": "EXITO"}, "resultado"),
        ({"usuario_id": "no-es-uuid"}, "usuario_id"),
        ({"desde": "ayer"}, "desde"),
        ({"desde": "2026-10-01T00:00:00"}, "desde"),  # sin zona horaria
        ({"accion": "X" * 51}, "accion"),
        ({"servicio_origen": "s" * 51}, "servicio_origen"),
    ],
    ids=[
        "tamano_grande",
        "tamano_cero",
        "pagina_cero",
        "resultado_invalido",
        "usuario_id_invalido",
        "fecha_invalida",
        "fecha_sin_zona",
        "accion_larga",
        "servicio_largo",
    ],
)
def test_filtro_invalido_422(
    client: TestClient,
    uow: FakeUnitOfWork,
    admin: dict[str, str],
    params: dict[str, object],
    campo: str,
) -> None:
    response = client.get(URL, params=params, headers=admin)

    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "VALIDACION"
    assert [e["campo"] for e in data["errores"]] == [campo]
    assert uow.auditoria.filtros == []
    assert uow.auditoria.registros == []


@pytest.mark.parametrize(
    "hasta", ["2026-10-01T00:00:00Z", "2026-09-30T00:00:00Z"], ids=["igual", "anterior"]
)
def test_rango_invertido_422(
    client: TestClient, uow: FakeUnitOfWork, admin: dict[str, str], hasta: str
) -> None:
    response = client.get(
        URL, params={"desde": "2026-10-01T00:00:00Z", "hasta": hasta}, headers=admin
    )

    assert response.status_code == 422
    assert response.json()["code"] == "RANGO_FECHAS_INVALIDO"
    assert uow.auditoria.filtros == []
    assert uow.auditoria.registros == []
