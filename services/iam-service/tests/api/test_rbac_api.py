from fastapi.testclient import TestClient

from app.domain.value_objects.enums import Rol
from tests.api.conftest import TOKEN_INVALIDO, bearer, emitir, unico_denegado
from tests.fakes import FakeRevocacion, FakeUnitOfWork

PING = "/api/iam/admin/ping"


def test_admin_200(client: TestClient, uow: FakeUnitOfWork) -> None:
    emitido, _ = emitir(client, Rol.ADMIN)

    response = client.get(PING, headers=bearer(emitido.access_token))

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert uow.entradas == 0


def test_turista_403_con_fila_en_la_bitacora(client: TestClient, uow: FakeUnitOfWork) -> None:
    emitido, u = emitir(client, Rol.TURISTA)

    response = client.get(PING + "?x=1", headers=bearer(emitido.access_token))

    assert response.status_code == 403
    assert response.json() == {
        "detail": "No tiene permisos para realizar esta acción.",
        "code": "ROL_INSUFICIENTE",
    }
    registro = unico_denegado(uow)
    assert registro.usuario_id == u.id
    assert registro.detalles == {
        "rol": "Turista",
        "requeridos": ["Admin"],
        "metodo": "GET",
        "ruta": PING,
        "plantilla": PING,
    }
    assert uow.commits == 1


def test_sin_token_401_con_fila(client: TestClient, uow: FakeUnitOfWork) -> None:
    response = client.get(PING)

    assert response.status_code == 401
    assert response.json() == TOKEN_INVALIDO
    assert response.headers["WWW-Authenticate"] == "Bearer"
    registro = unico_denegado(uow)
    assert registro.usuario_id is None
    assert registro.detalles == {"motivo": "sin_token", "metodo": "GET", "uri": PING}


def test_admin_revocado_401_con_fila(
    client: TestClient, uow: FakeUnitOfWork, revocacion: FakeRevocacion
) -> None:
    emitido, u = emitir(client, Rol.ADMIN)
    revocacion.revocados[emitido.jti] = emitido.expira_en

    response = client.get(PING, headers=bearer(emitido.access_token))

    assert response.status_code == 401
    registro = unico_denegado(uow)
    assert registro.usuario_id == u.id
    assert registro.detalles == {"motivo": "revocado", "metodo": "GET", "uri": PING}


def test_postgresql_caido_en_un_403_sigue_siendo_403(
    client: TestClient, uow: FakeUnitOfWork
) -> None:
    emitido, _ = emitir(client, Rol.TURISTA)
    uow.caida = True

    response = client.get(PING, headers=bearer(emitido.access_token))

    assert response.status_code == 403
    assert uow.auditoria.registros == []


def test_valkey_caido_503(client: TestClient, revocacion: FakeRevocacion) -> None:
    emitido, _ = emitir(client, Rol.ADMIN)
    revocacion.caida = True

    response = client.get(PING, headers=bearer(emitido.access_token))

    assert response.status_code == 503
    assert response.json()["code"] == "SERVICIO_NO_DISPONIBLE"
