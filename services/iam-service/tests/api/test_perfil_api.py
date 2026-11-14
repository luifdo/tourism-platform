"""UC4 por HTTP: perfil con ETag e If-Match, y cambio de contraseña (C-49, C-51, C-52)."""

import pytest
from fastapi.testclient import TestClient

from app.domain.value_objects.enums import ResultadoAuditoria, Rol
from tests.api.conftest import CLAVE, CORRELATION_ID, IP_CLIENTE, TOKEN_INVALIDO, cuenta_con_sesion
from tests.fakes import FakePasswordHasher, FakeRevocacion, FakeUnitOfWork

PERFIL = "/api/iam/perfil"
CONTRASENA = "/api/iam/perfil/contrasena"
NUEVA = "Nueva12345"


@pytest.mark.parametrize("rol", list(Rol))
def test_cualquier_rol_ve_su_perfil(
    client: TestClient, uow: FakeUnitOfWork, hasher: FakePasswordHasher, rol: Rol
) -> None:
    headers, u = cuenta_con_sesion(client, uow, hasher, rol, razon_social="Tayrona SAS")

    response = client.get(PERFIL, headers=headers)

    assert response.status_code == 200
    assert response.headers["etag"] == '"1"'
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert set(data) == {"id", "email", "nombre", "rol", "idioma", "razon_social", "creado_en"}
    assert data["id"] == str(u.id)
    assert (data["nombre"], data["rol"], data["razon_social"]) == (
        "María Pérez",
        rol.value,
        "Tayrona SAS",
    )


def test_sin_token_401(client: TestClient) -> None:
    response = client.get(PERFIL)

    assert response.status_code == 401
    assert response.json() == TOKEN_INVALIDO


def test_patch_cambia_audita_solo_los_nombres_y_sube_la_version(
    client: TestClient, uow: FakeUnitOfWork, hasher: FakePasswordHasher
) -> None:
    headers, u = cuenta_con_sesion(client, uow, hasher)

    response = client.patch(
        PERFIL, json={"nombre": "  María Gómez ", "idioma": "en"}, headers=headers
    )

    assert response.status_code == 200
    assert response.headers["etag"] == '"2"'
    assert (response.json()["nombre"], response.json()["idioma"]) == ("María Gómez", "en")
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("PROFILE_UPDATE", ResultadoAuditoria.EXITO)
    assert (registro.usuario_id, registro.ip_origen) == (u.id, IP_CLIENTE)
    assert registro.detalles == {"campos": ["nombre", "idioma"]}
    assert "María" not in str(registro.detalles)


def test_patch_de_un_solo_campo_conserva_el_otro(
    client: TestClient, uow: FakeUnitOfWork, hasher: FakePasswordHasher
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher)

    response = client.patch(PERFIL, json={"idioma": "en"}, headers=headers)

    assert (response.json()["nombre"], response.json()["idioma"]) == ("María Pérez", "en")
    assert uow.auditoria.registros[0].detalles == {"campos": ["idioma"]}


@pytest.mark.parametrize("cuerpo", [{}, {"nombre": "María Pérez"}, {"idioma": "es"}])
def test_sin_cambios_200_sin_auditar_ni_subir_la_version(
    client: TestClient, uow: FakeUnitOfWork, hasher: FakePasswordHasher, cuerpo: dict[str, str]
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher)

    response = client.patch(PERFIL, json=cuerpo, headers=headers)

    assert response.status_code == 200
    assert response.headers["etag"] == '"1"'
    assert uow.auditoria.registros == []


@pytest.mark.parametrize("if_match", ['"1"', 'W/"1"', "1", "*"])
def test_if_match_que_coincide(
    client: TestClient, uow: FakeUnitOfWork, hasher: FakePasswordHasher, if_match: str
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher)

    response = client.patch(
        PERFIL, json={"idioma": "en"}, headers={**headers, "If-Match": if_match}
    )

    assert response.status_code == 200


@pytest.mark.parametrize("if_match", ['"7"', "basura", '"1", "2"'])
def test_if_match_que_no_coincide_409_sin_cambiar_nada(
    client: TestClient, uow: FakeUnitOfWork, hasher: FakePasswordHasher, if_match: str
) -> None:
    headers, u = cuenta_con_sesion(client, uow, hasher)

    response = client.patch(
        PERFIL, json={"idioma": "en"}, headers={**headers, "If-Match": if_match}
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "El perfil cambió desde la última vez que se consultó.",
        "code": "VERSION_CONFLICTO",
        "correlation_id": CORRELATION_ID,
    }
    assert uow.usuarios.por_email[u.email].idioma.value == "es"
    assert uow.auditoria.registros == []


def test_reenviar_el_mismo_patch_con_el_if_match_viejo_no_es_conflicto(
    client: TestClient, uow: FakeUnitOfWork, hasher: FakePasswordHasher
) -> None:
    # La cola sin conexión reenvía si se perdió la respuesta: RNF-13, sin Idempotency-Key (C-49).
    headers, _ = cuenta_con_sesion(client, uow, hasher)
    envio = {"json": {"nombre": "María Gómez"}, "headers": {**headers, "If-Match": '"1"'}}

    primero = client.patch(PERFIL, **envio)
    segundo = client.patch(PERFIL, **envio)

    assert (primero.status_code, segundo.status_code) == (200, 200)
    assert primero.json() == segundo.json()
    assert segundo.headers["etag"] == '"2"'
    assert len(uow.auditoria.registros) == 1


def test_otro_cambio_con_el_if_match_viejo_si_es_conflicto(
    client: TestClient, uow: FakeUnitOfWork, hasher: FakePasswordHasher
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher)
    con_version = {**headers, "If-Match": '"1"'}
    client.patch(PERFIL, json={"nombre": "María Gómez"}, headers=con_version)

    response = client.patch(PERFIL, json={"nombre": "Otra Persona"}, headers=con_version)

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("cuerpo", "code"),
    [
        ({"nombre": "x"}, "NOMBRE_INVALIDO"),
        ({"nombre": "   "}, "NOMBRE_INVALIDO"),
        ({"nombre": "x" * 151}, "NOMBRE_INVALIDO"),
        ({"idioma": "fr"}, "VALIDACION"),
        ({"email": "otro@example.com"}, "VALIDACION"),
        ({"razon_social": "Otra SAS"}, "VALIDACION"),
    ],
)
def test_reglas_del_registro_y_campos_que_no_se_editan(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    cuerpo: dict[str, str],
    code: str,
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher)

    response = client.patch(PERFIL, json=cuerpo, headers=headers)

    assert response.status_code == 422
    assert response.json()["code"] == code


# ---------- Cambio de contraseña ----------


def test_cambiar_contrasena_204_guarda_el_hash_y_revoca_los_tokens_anteriores(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    revocacion: FakeRevocacion,
) -> None:
    headers, u = cuenta_con_sesion(client, uow, hasher)
    assert client.get(PERFIL, headers=headers).status_code == 200

    response = client.post(
        CONTRASENA, json={"password_actual": CLAVE, "password_nueva": NUEVA}, headers=headers
    )

    assert response.status_code == 204
    assert response.content == b""
    assert hasher.verify(NUEVA, uow.usuarios.por_email[u.email].password_hash)
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("PASSWORD_CHANGE", ResultadoAuditoria.EXITO)
    assert registro.detalles == {}
    # Doble revocación por usuario (C-21), y el token con el que se pidió ya no sirve.
    assert len(revocacion.revocaciones_usuario) == 2
    assert client.get(PERFIL, headers=headers).status_code == 401


def test_contrasena_actual_incorrecta_422_con_su_fila_denegada(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    revocacion: FakeRevocacion,
) -> None:
    headers, u = cuenta_con_sesion(client, uow, hasher)

    response = client.post(
        CONTRASENA, json={"password_actual": "Mala12345", "password_nueva": NUEVA}, headers=headers
    )

    assert response.status_code == 422
    assert response.json()["code"] == "PASSWORD_ACTUAL_INCORRECTA"
    assert "www-authenticate" not in response.headers
    assert hasher.verify(CLAVE, uow.usuarios.por_email[u.email].password_hash)
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("PASSWORD_CHANGE", ResultadoAuditoria.DENEGADO)
    assert uow.commits == 1
    assert revocacion.revocaciones_usuario == []


def test_contrasena_nueva_debil_422_sin_cambiar_nada(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    revocacion: FakeRevocacion,
) -> None:
    headers, u = cuenta_con_sesion(client, uow, hasher)

    response = client.post(
        CONTRASENA, json={"password_actual": CLAVE, "password_nueva": "corta"}, headers=headers
    )

    assert response.status_code == 422
    assert response.json()["code"] == "PASSWORD_INVALIDA"
    assert hasher.verify(CLAVE, uow.usuarios.por_email[u.email].password_hash)
    assert revocacion.revocaciones_usuario == []


def test_valkey_caido_al_cambiar_contrasena_503(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    revocacion: FakeRevocacion,
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher)
    revocacion.caida = True

    response = client.post(
        CONTRASENA, json={"password_actual": CLAVE, "password_nueva": NUEVA}, headers=headers
    )

    assert response.status_code == 503
