import uuid
from dataclasses import replace
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import ResultadoAuditoria
from tests.api.conftest import CLAVE, IP_CLIENTE, TOKEN_INVALIDO, bearer, usuario
from tests.fakes import AHORA, FakePasswordHasher, FakeSesionesRenovacion, FakeUnitOfWork

LOGIN = "/api/iam/login"
LOGOUT = "/api/iam/logout"
REFRESH = "/api/iam/auth/refresh"
VERIFICAR = "/api/iam/auth/verificar"
EMAIL = "maria.perez@example.com"


def sembrar(uow: FakeUnitOfWork, hasher: FakePasswordHasher) -> Usuario:
    return uow.usuarios.sembrar(replace(usuario(), email=EMAIL, password_hash=hasher.hash(CLAVE)))


def login(client: TestClient) -> dict[str, Any]:
    respuesta = client.post(LOGIN, json={"email": EMAIL, "password": CLAVE})
    assert respuesta.status_code == 200
    return respuesta.json()


def renovar(client: TestClient, token: str) -> Any:
    return client.post(REFRESH, json={"refresh_token": token})


def sid_de(access_token: str) -> str:
    return jwt.decode(access_token, options={"verify_signature": False})["sid"]


def contador(resultado: str) -> float:
    return REGISTRY.get_sample_value("iam_refresh_total", {"resultado": resultado}) or 0.0


def filas(uow: FakeUnitOfWork, accion: str) -> list[Any]:
    return [r for r in uow.auditoria.registros if r.accion == accion]


@pytest.fixture
def cuenta(uow: FakeUnitOfWork, hasher: FakePasswordHasher) -> Usuario:
    return sembrar(uow, hasher)


def test_login_entrega_el_refresh_y_el_access_lleva_el_sid(
    client: TestClient, cuenta: Usuario, sesiones: FakeSesionesRenovacion
) -> None:
    data = login(client)

    assert data["refresh_expires_in"] == FakeSesionesRenovacion.TTL
    assert sid_de(data["access_token"]) in sesiones.familias


def test_ok_responde_como_el_login_con_tokens_nuevos(
    client: TestClient, uow: FakeUnitOfWork, cuenta: Usuario
) -> None:
    inicial = login(client)
    antes = contador("ok")
    filas_antes = len(uow.auditoria.registros)

    respuesta = renovar(client, inicial["refresh_token"])

    assert respuesta.status_code == 200
    assert respuesta.headers["Cache-Control"] == "no-store"
    data = respuesta.json()
    assert set(data) == set(inicial)
    assert data["refresh_token"] != inicial["refresh_token"]
    assert data["access_token"] != inicial["access_token"]
    assert sid_de(data["access_token"]) == sid_de(inicial["access_token"])
    assert data["usuario"]["id"] == str(cuenta.id)
    assert client.get(VERIFICAR, headers=bearer(data["access_token"])).status_code == 200
    # Sin fila: sería una cada 15 minutos por usuario. Solo la métrica.
    assert len(uow.auditoria.registros) == filas_antes
    assert contador("ok") == antes + 1


def test_invalido_401_con_fila_access_denied(client: TestClient, uow: FakeUnitOfWork) -> None:
    antes = contador("invalido")

    respuesta = renovar(client, "no-existe")

    assert respuesta.status_code == 401
    assert respuesta.json() == TOKEN_INVALIDO
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("ACCESS_DENIED", ResultadoAuditoria.DENEGADO)
    assert (registro.usuario_id, registro.ip_origen) == (None, IP_CLIENTE)
    assert registro.detalles == {"motivo": "invalido", "metodo": "POST", "uri": REFRESH}
    assert contador("invalido") == antes + 1


def test_revocado_401_con_fila_y_usuario(
    client: TestClient, uow: FakeUnitOfWork, cuenta: Usuario
) -> None:
    inicial = login(client)
    assert client.post(LOGOUT, headers=bearer(inicial["access_token"])).status_code == 204
    antes = contador("revocado")

    respuesta = renovar(client, inicial["refresh_token"])

    assert respuesta.status_code == 401
    assert respuesta.json() == TOKEN_INVALIDO
    [registro] = filas(uow, "ACCESS_DENIED")
    assert registro.usuario_id == cuenta.id
    assert registro.detalles == {"motivo": "revocado", "metodo": "POST", "uri": REFRESH}
    assert contador("revocado") == antes + 1


def test_reutilizado_401_con_su_fila_y_mismo_cuerpo(
    client: TestClient, uow: FakeUnitOfWork, cuenta: Usuario, sesiones: FakeSesionesRenovacion
) -> None:
    inicial = login(client)
    familia = sid_de(inicial["access_token"])
    segundo = renovar(client, inicial["refresh_token"]).json()
    antes = contador("reutilizado")

    respuesta = renovar(client, inicial["refresh_token"])

    assert respuesta.status_code == 401
    assert respuesta.json() == TOKEN_INVALIDO
    assert sesiones.revocada(familia) is True
    assert filas(uow, "ACCESS_DENIED") == []
    [registro] = filas(uow, "REFRESH_REUTILIZADO")
    assert registro.resultado is ResultadoAuditoria.DENEGADO
    assert (registro.usuario_id, registro.ip_origen) == (cuenta.id, IP_CLIENTE)
    assert registro.detalles == {"familia": familia}
    assert contador("reutilizado") == antes + 1

    # El token que era el vigente también cae, y no es otro robo.
    nuevo = renovar(client, segundo["refresh_token"])
    assert nuevo.status_code == 401
    assert filas(uow, "ACCESS_DENIED")[0].detalles["motivo"] == "revocado"
    assert len(filas(uow, "REFRESH_REUTILIZADO")) == 1


def test_las_tres_causas_responden_identico_byte_a_byte(
    client: TestClient, cuenta: Usuario
) -> None:
    primero = login(client)
    renovar(client, primero["refresh_token"])
    reutilizado = renovar(client, primero["refresh_token"])
    segundo = login(client)
    client.post(LOGOUT, headers=bearer(segundo["access_token"]))
    revocado = renovar(client, segundo["refresh_token"])
    invalido = renovar(client, "no-existe")

    assert reutilizado.status_code == revocado.status_code == invalido.status_code == 401
    assert reutilizado.content == revocado.content == invalido.content


def test_tras_reutilizado_el_access_de_esa_sesion_recibe_401_y_otra_sigue_en_200(
    client: TestClient, uow: FakeUnitOfWork, cuenta: Usuario
) -> None:
    robada = login(client)
    otra_sesion = login(client)
    renovada = renovar(client, robada["refresh_token"]).json()
    assert renovar(client, robada["refresh_token"]).status_code == 401
    filas_antes = len(uow.auditoria.registros)

    # El emitido al iniciar sesión y el de la renovación: los dos llevan ese sid.
    for token in (robada["access_token"], renovada["access_token"]):
        respuesta = client.get(VERIFICAR, headers=bearer(token))
        assert respuesta.status_code == 401
    rechazos = uow.auditoria.registros[filas_antes:]
    assert [r.detalles["motivo"] for r in rechazos] == ["revocado", "revocado"]
    assert {r.usuario_id for r in rechazos} == {cuenta.id}

    respuesta = client.get(VERIFICAR, headers=bearer(otra_sesion["access_token"]))
    assert respuesta.status_code == 200
    assert renovar(client, otra_sesion["refresh_token"]).status_code == 200


def test_logout_invalida_los_tokens_de_la_sesion_sin_cerrar_las_otras(
    client: TestClient, cuenta: Usuario
) -> None:
    sesion = login(client)
    otra = login(client)
    renovada = renovar(client, sesion["refresh_token"]).json()

    assert client.post(LOGOUT, headers=bearer(renovada["access_token"])).status_code == 204

    # También el access token anterior, que el logout no presentó.
    assert client.get(VERIFICAR, headers=bearer(sesion["access_token"])).status_code == 401
    assert renovar(client, renovada["refresh_token"]).status_code == 401
    assert client.get(VERIFICAR, headers=bearer(otra["access_token"])).status_code == 200
    assert renovar(client, otra["refresh_token"]).status_code == 200


@pytest.mark.parametrize(
    "campos",
    [{"activo": False}, {"activo": False, "datos_suprimidos_en": AHORA}],
    ids=["inactiva", "suprimida"],
)
def test_cuenta_inactiva_o_suprimida_401_con_fila(
    client: TestClient,
    uow: FakeUnitOfWork,
    cuenta: Usuario,
    sesiones: FakeSesionesRenovacion,
    campos: dict[str, Any],
) -> None:
    inicial = login(client)
    uow.usuarios.por_email[EMAIL] = replace(uow.usuarios.por_email[EMAIL], **campos)

    respuesta = renovar(client, inicial["refresh_token"])

    assert respuesta.status_code == 401
    assert respuesta.json() == TOKEN_INVALIDO
    assert sesiones.revocada(sid_de(inicial["access_token"])) is True
    [registro] = filas(uow, "ACCESS_DENIED")
    assert (registro.usuario_id, registro.detalles["motivo"]) == (cuenta.id, "revocado")


def test_refresh_revocado_por_usuario(
    client: TestClient, uow: FakeUnitOfWork, cuenta: Usuario, sesiones: FakeSesionesRenovacion
) -> None:
    inicial = login(client)
    assert cuenta.id is not None
    # La marca es el mismo segundo o posterior: revoca también lo emitido en ese segundo.
    sesiones.revocacion.revocados_desde[cuenta.id] = sesiones.familias[
        sid_de(inicial["access_token"])
    ]["renovado_en"]

    respuesta = renovar(client, inicial["refresh_token"])

    assert respuesta.status_code == 401
    assert filas(uow, "ACCESS_DENIED")[0].detalles["motivo"] == "revocado"
    assert sesiones.revocada(sid_de(inicial["access_token"])) is True


@pytest.mark.parametrize(
    "cuerpo",
    [{}, {"refresh_token": ""}, {"refresh_token": "x" * 129}, {"refresh_token": 123}],
    ids=["falta", "vacio", "129", "no_es_cadena"],
)
def test_422_sin_tocar_valkey_ni_repetir_el_valor(
    client: TestClient, sesiones: FakeSesionesRenovacion, cuerpo: dict[str, Any]
) -> None:
    sesiones.caida = True  # si llegara a Valkey, sería 503

    respuesta = client.post(REFRESH, json=cuerpo)

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "VALIDACION"
    assert "x" * 129 not in respuesta.text


def test_admite_128_caracteres(client: TestClient) -> None:
    assert renovar(client, "x" * 128).status_code == 401


def test_503_si_valkey_no_responde_sin_fila(
    client: TestClient, uow: FakeUnitOfWork, sesiones: FakeSesionesRenovacion
) -> None:
    sesiones.caida = True

    respuesta = renovar(client, "cualquiera")

    assert respuesta.status_code == 503
    assert respuesta.json()["code"] == "SERVICIO_NO_DISPONIBLE"
    assert uow.auditoria.registros == []


def test_503_si_postgres_falla_tras_rotar(
    client: TestClient, uow: FakeUnitOfWork, cuenta: Usuario, sesiones: FakeSesionesRenovacion
) -> None:
    inicial = login(client)
    uow.caida = True

    respuesta = renovar(client, inicial["refresh_token"])

    assert respuesta.status_code == 503
    assert respuesta.json()["code"] == "SERVICIO_NO_DISPONIBLE"
    assert sesiones.revocada(sid_de(inicial["access_token"])) is True


def test_el_refresh_opaco_no_sirve_como_bearer(client: TestClient, cuenta: Usuario) -> None:
    inicial = login(client)

    respuesta = client.get(VERIFICAR, headers=bearer(inicial["refresh_token"]))

    assert respuesta.status_code == 401


def test_no_exige_autenticacion(client: TestClient, cuenta: Usuario) -> None:
    inicial = login(client)

    respuesta = client.post(
        REFRESH,
        json={"refresh_token": inicial["refresh_token"]},
        headers=bearer(f"token-vencido-{uuid.uuid4()}"),
    )

    assert respuesta.status_code == 200
