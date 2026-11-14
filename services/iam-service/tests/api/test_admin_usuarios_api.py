"""UC27 por HTTP: /api/iam/admin/usuarios (C-29, C-17, C-21)."""

import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.domain.entities.usuario import Usuario
from app.domain.events.prestador_suspendido import PrestadorSuspendido
from app.domain.value_objects.enums import Rol
from tests.api.conftest import CORRELATION_ID, IP_CLIENTE, bearer, emitir, usuario
from tests.fakes import FakeRevocacion, FakeUnitOfWork

BASE = "/api/iam/admin/usuarios"


def guardar(uow: FakeUnitOfWork, u: Usuario) -> Usuario:
    """Guarda la cuenta con su id (sembrar() asigna uno nuevo)."""
    uow.usuarios.por_email[u.email] = replace(
        u, creado_en=u.habeas_data_aceptado_en, actualizado_en=u.habeas_data_aceptado_en
    )
    return uow.usuarios.por_email[u.email]


@pytest.fixture
def admin(client: TestClient, uow: FakeUnitOfWork) -> dict[str, str]:
    emitido, u = emitir(client, Rol.ADMIN)
    guardar(uow, replace(u, email="admin@example.com"))
    return bearer(emitido.access_token)


@pytest.fixture
def prestador(uow: FakeUnitOfWork) -> Usuario:
    return guardar(uow, replace(usuario(Rol.PRESTADOR), email="prestador@example.com"))


def test_listar_con_filtros_y_paginacion(
    client: TestClient, uow: FakeUnitOfWork, admin: dict[str, str], prestador: Usuario
) -> None:
    for i in range(3):
        guardar(uow, replace(usuario(), email=f"turista{i}@example.com"))

    response = client.get(BASE, params={"rol": "Turista", "pagina": 2, "tamano": 2}, headers=admin)

    assert response.status_code == 200
    data = response.json()
    assert (data["total"], data["pagina"], data["tamano"]) == (3, 2, 2)
    [item] = data["items"]
    assert set(item) == {
        "id",
        "email",
        "nombre_completo",
        "rol",
        "activo",
        "email_verificado",
        "idioma",
        "creado_en",
        "actualizado_en",
    }
    assert item["rol"] == "Turista"
    assert "password_hash" not in response.text


@pytest.mark.parametrize(
    "params",
    [{"tamano": 101}, {"tamano": 0}, {"pagina": 0}, {"rol": "Root"}, {"q": "x" * 101}],
    ids=["tamano_grande", "tamano_cero", "pagina_cero", "rol_invalido", "q_largo"],
)
def test_listar_422(client: TestClient, admin: dict[str, str], params: dict[str, object]) -> None:
    response = client.get(BASE, params=params, headers=admin)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDACION"


def test_obtener_200_y_404(client: TestClient, admin: dict[str, str], prestador: Usuario) -> None:
    assert client.get(f"{BASE}/{prestador.id}", headers=admin).json()["rol"] == "Prestador"

    response = client.get(f"{BASE}/{uuid.uuid4()}", headers=admin)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "El usuario no existe.",
        "code": "USUARIO_NO_ENCONTRADO",
        "correlation_id": CORRELATION_ID,
    }


def test_desactivar_prestador(
    client: TestClient,
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    admin: dict[str, str],
    prestador: Usuario,
) -> None:
    response = client.patch(
        f"{BASE}/{prestador.id}/estado",
        json={"activo": False, "motivo": "RNT vencido"},
        headers=admin,
    )

    assert response.status_code == 200
    assert response.json()["activo"] is False
    [registro] = uow.auditoria.registros
    assert registro.accion == "USER_STATUS_CHANGE"
    assert registro.ip_origen == IP_CLIENTE
    assert registro.correlation_id == CORRELATION_ID
    assert registro.detalles["motivo"] == "RNT vencido"
    [evento] = uow.outbox.eventos
    assert isinstance(evento, PrestadorSuspendido)
    assert len(revocacion.revocaciones_usuario) == 2


def test_cambiar_rol(
    client: TestClient, uow: FakeUnitOfWork, admin: dict[str, str], prestador: Usuario
) -> None:
    response = client.patch(f"{BASE}/{prestador.id}/rol", json={"rol": "Entidad"}, headers=admin)

    assert response.status_code == 200
    assert response.json()["rol"] == "Entidad"
    assert uow.auditoria.registros[0].accion == "ROLE_CHANGE"
    assert len(uow.outbox.eventos) == 1


def test_sin_efecto_200_sin_auditar(
    client: TestClient, uow: FakeUnitOfWork, admin: dict[str, str], prestador: Usuario
) -> None:
    response = client.patch(f"{BASE}/{prestador.id}/rol", json={"rol": "Prestador"}, headers=admin)

    assert response.status_code == 200
    assert uow.auditoria.registros == []
    assert uow.outbox.eventos == []


def test_autogestion_409(client: TestClient, uow: FakeUnitOfWork, admin: dict[str, str]) -> None:
    propio = uow.usuarios.por_email["admin@example.com"]

    response = client.patch(f"{BASE}/{propio.id}/estado", json={"activo": False}, headers=admin)

    assert response.status_code == 409
    assert response.json()["code"] == "AUTOGESTION_NO_PERMITIDA"


def test_ultimo_admin_409(client: TestClient, uow: FakeUnitOfWork, admin: dict[str, str]) -> None:
    propio = uow.usuarios.por_email["admin@example.com"]
    uow.usuarios.por_email[propio.email] = replace(propio, activo=False)
    unico = guardar(uow, replace(usuario(Rol.ADMIN), email="unico@example.com"))

    response = client.patch(f"{BASE}/{unico.id}/rol", json={"rol": "Turista"}, headers=admin)

    assert response.status_code == 409
    assert response.json()["code"] == "ULTIMO_ADMIN"


def test_valkey_caido_503_sin_cambios(
    client: TestClient,
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    admin: dict[str, str],
    prestador: Usuario,
) -> None:
    # verificar el token del Admin ya pasó: Valkey cae justo al revocar.
    def caer() -> None:
        revocacion.caida = True

    revocacion.al_revocar_usuario = caer

    response = client.patch(f"{BASE}/{prestador.id}/estado", json={"activo": False}, headers=admin)

    assert response.status_code == 503
    assert response.json()["code"] == "SERVICIO_NO_DISPONIBLE"
    assert uow.commits == 0


@pytest.mark.parametrize(
    ("ruta", "body"),
    [
        ("rol", {"rol": "Root"}),
        ("rol", {}),
        ("estado", {"activo": "quizas"}),
        ("estado", {"activo": False, "motivo": "x" * 2001}),
    ],
    ids=["rol_invalido", "sin_rol", "activo_invalido", "motivo_muy_largo"],
)
def test_cambios_422(
    client: TestClient,
    uow: FakeUnitOfWork,
    admin: dict[str, str],
    prestador: Usuario,
    ruta: str,
    body: dict[str, object],
) -> None:
    response = client.patch(f"{BASE}/{prestador.id}/{ruta}", json=body, headers=admin)

    assert response.status_code == 422
    assert uow.commits == 0


def test_uuid_mal_formado_422(client: TestClient, admin: dict[str, str]) -> None:
    response = client.patch(f"{BASE}/no-es-uuid/rol", json={"rol": "Turista"}, headers=admin)

    assert response.status_code == 422


def test_turista_403(client: TestClient, prestador: Usuario) -> None:
    emitido, _ = emitir(client, Rol.TURISTA)

    response = client.patch(
        f"{BASE}/{prestador.id}/estado",
        json={"activo": False},
        headers=bearer(emitido.access_token),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "ROL_INSUFICIENTE"


def test_ping_ya_no_existe(client: TestClient, admin: dict[str, str]) -> None:
    assert client.get("/api/iam/admin/ping", headers=admin).status_code == 404
