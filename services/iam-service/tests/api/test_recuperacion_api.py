"""UC3 por HTTP: recuperar y restablecer, con los cuerpos que ya envía la PWA (C-28, C-50)."""

import re
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import Idioma, ResultadoAuditoria, Rol
from tests.api.conftest import (
    CLAVE,
    CORRELATION_ID,
    IP_CLIENTE,
    cuenta_con_sesion,
    esperar_tareas,
    usuario,
)
from tests.fakes import (
    AHORA,
    FakeEnviadorCorreo,
    FakePasswordHasher,
    FakeRevocacion,
    FakeTokensRecuperacion,
    FakeUnitOfWork,
)

RECUPERAR = "/api/iam/auth/recuperar"
RESTABLECER = "/api/iam/auth/restablecer"
EMAIL = "maria.perez@example.com"
NUEVA = "Nueva12345"


def sembrar(uow: FakeUnitOfWork, hasher: FakePasswordHasher, **campos) -> Usuario:  # type: ignore[no-untyped-def]
    return uow.usuarios.sembrar(
        replace(usuario(), email=EMAIL, password_hash=hasher.hash(CLAVE), **campos)
    )


def token_del_correo(enviador: FakeEnviadorCorreo) -> str:
    coincidencia = re.search(r"\?token=([\w-]+)", enviador.enviados[-1].texto)
    assert coincidencia is not None
    return coincidencia.group(1)


def resultado(nombre: str) -> float:
    return (
        REGISTRY.get_sample_value("iam_recuperacion_solicitudes_total", {"resultado": nombre}) or 0
    )


# ---------- Recuperar ----------


def test_recuperar_envia_el_correo_y_audita(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
    tokens_recuperacion: FakeTokensRecuperacion,
) -> None:
    u = sembrar(uow, hasher)

    response = client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)

    assert response.status_code == 202
    [correo] = enviador.enviados
    assert correo.destinatario == EMAIL
    # El enlace sale de PWA_URL, no del Host de la petición.
    assert "http://localhost:5173/restablecer-contrasena?token=" in correo.texto
    assert "testserver" not in correo.texto + correo.html
    assert tokens_recuperacion.tokens == {token_del_correo(enviador): u.id}
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == (
        "PASSWORD_RESET_REQUEST",
        ResultadoAuditoria.EXITO,
    )
    assert (registro.usuario_id, registro.ip_origen) == (u.id, IP_CLIENTE)
    assert registro.correlation_id == CORRELATION_ID
    assert EMAIL not in str(registro.detalles)


@pytest.mark.parametrize(
    "preparar",
    [
        pytest.param(lambda uow, hasher: sembrar(uow, hasher), id="existente"),
        pytest.param(lambda uow, hasher: None, id="inexistente"),
        pytest.param(lambda uow, hasher: sembrar(uow, hasher, activo=False), id="inactivo"),
        pytest.param(
            lambda uow, hasher: sembrar(uow, hasher, activo=False, datos_suprimidos_en=AHORA),
            id="suprimido",
        ),
    ],
)
def test_misma_respuesta_sin_esperar_al_trabajo(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
    preparar,  # type: ignore[no-untyped-def]
) -> None:
    preparar(uow, hasher)
    # El SMTP no termina hasta soltarlo (o hasta su tope de 10 s).
    enviador.liberar.clear()

    response = client.post(RECUPERAR, json={"email": EMAIL})

    # Sin soltar el SMTP: si la respuesta lo hubiera esperado, aquí ya habría un correo.
    assert enviador.enviados == []
    # Comparar el cuerpo contra una constante cubre los cuatro casos a la vez.
    assert response.status_code == 202
    assert response.json() == {
        "detail": "Si el correo está registrado, recibirá un enlace para restablecer la contraseña."
    }
    enviador.liberar.set()
    esperar_tareas(client)


@pytest.mark.parametrize(
    "preparar",
    [
        pytest.param(lambda uow, hasher: None, id="inexistente"),
        pytest.param(lambda uow, hasher: sembrar(uow, hasher, activo=False), id="inactivo"),
        pytest.param(
            lambda uow, hasher: sembrar(uow, hasher, activo=False, datos_suprimidos_en=AHORA),
            id="suprimido",
        ),
    ],
)
def test_no_elegible_no_envia_ni_audita_ni_guarda_token(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
    tokens_recuperacion: FakeTokensRecuperacion,
    preparar,  # type: ignore[no-untyped-def]
) -> None:
    preparar(uow, hasher)
    antes = resultado("no_elegible")

    client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)

    assert enviador.enviados == []
    assert uow.auditoria.registros == []
    assert tokens_recuperacion.tokens == {}
    assert resultado("no_elegible") == antes + 1


def test_correo_con_formato_invalido_tambien_202(
    client: TestClient, enviador: FakeEnviadorCorreo
) -> None:
    response = client.post(RECUPERAR, json={"email": "no-es-un-correo"})
    esperar_tareas(client)

    assert response.status_code == 202
    assert enviador.enviados == []


def test_enfriamiento_no_envia_otro_correo_ni_invalida_el_enlace(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
) -> None:
    sembrar(uow, hasher)
    antes = resultado("enfriamiento")
    client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)
    primero = token_del_correo(enviador)

    response = client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)

    assert response.status_code == 202
    assert len(enviador.enviados) == 1
    assert len(uow.auditoria.registros) == 1
    assert resultado("enfriamiento") == antes + 1
    assert client.post(RESTABLECER, json={"token": primero, "password": NUEVA}).status_code == 204


def test_solicitud_nueva_invalida_la_anterior(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
    tokens_recuperacion: FakeTokensRecuperacion,
) -> None:
    u = sembrar(uow, hasher)
    client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)
    viejo = token_del_correo(enviador)
    tokens_recuperacion.en_espera.discard(u.id)  # type: ignore[arg-type]

    client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)

    assert client.post(RESTABLECER, json={"token": viejo, "password": NUEVA}).status_code == 400
    nuevo = token_del_correo(enviador)
    assert client.post(RESTABLECER, json={"token": nuevo, "password": NUEVA}).status_code == 204


def test_fallo_de_smtp_202_con_metrica_y_se_puede_pedir_de_nuevo(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
    tokens_recuperacion: FakeTokensRecuperacion,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sembrar(uow, hasher)
    enviador.caido = True
    antes = resultado("fallo_smtp")

    response = client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)

    assert response.status_code == 202
    assert resultado("fallo_smtp") == antes + 1
    assert tokens_recuperacion.tokens == {}
    assert EMAIL not in caplog.text

    # No se envió nada: el enfriamiento no le impide volver a pedirlo.
    enviador.caido = False
    client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)
    assert len(enviador.enviados) == 1


def test_valkey_caido_202_con_metrica(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
    tokens_recuperacion: FakeTokensRecuperacion,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sembrar(uow, hasher)
    tokens_recuperacion.caido = True
    antes = resultado("fallo_valkey")

    response = client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)

    assert response.status_code == 202
    assert resultado("fallo_valkey") == antes + 1
    assert enviador.enviados == []
    assert EMAIL not in caplog.text


def test_base_caida_202_con_metrica(client: TestClient, uow: FakeUnitOfWork) -> None:
    uow.caida = True
    antes = resultado("fallo_base")

    response = client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)

    assert response.status_code == 202
    assert resultado("fallo_base") == antes + 1


@pytest.mark.parametrize(
    ("idioma", "frase"),
    [(Idioma.ES, "ignora este correo"), (Idioma.EN, "ignore this email")],
)
def test_correo_en_el_idioma_del_usuario_con_texto_y_html(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
    idioma: Idioma,
    frase: str,
) -> None:
    sembrar(uow, hasher, idioma=idioma, nombre_completo="<b>María</b>")

    client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)

    [correo] = enviador.enviados
    assert frase in correo.texto and frase in correo.html
    assert "30" in correo.texto and "30" in correo.html
    assert "<a href=" in correo.html
    # El nombre lo escribe el usuario: no inyecta HTML.
    assert "<b>María</b>" not in correo.html
    assert "&lt;b&gt;María&lt;/b&gt;" in correo.html


# ---------- Restablecer ----------


def preparar_enlace(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
) -> tuple[str, Usuario]:
    u = sembrar(uow, hasher)
    client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)
    uow.auditoria.registros.clear()
    return token_del_correo(enviador), u


def test_restablecer_guarda_revoca_y_audita(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
    revocacion: FakeRevocacion,
) -> None:
    token, u = preparar_enlace(client, uow, hasher, enviador)

    # Mismo cuerpo que ResetView.vue, aunque httpAuthGateway hoy solo envía token y password.
    response = client.post(
        RESTABLECER, json={"token": token, "password": NUEVA, "confirmacion": NUEVA}
    )

    assert response.status_code == 204
    assert hasher.verify(NUEVA, uow.usuarios.por_email[EMAIL].password_hash)
    assert [r for r, _ in revocacion.revocaciones_usuario] == [u.id, u.id]
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("PASSWORD_RESET", ResultadoAuditoria.EXITO)
    assert (registro.usuario_id, registro.ip_origen) == (u.id, IP_CLIENTE)
    assert token not in str(registro.detalles)


def test_el_enlace_es_de_un_solo_uso(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
) -> None:
    token, _ = preparar_enlace(client, uow, hasher, enviador)
    client.post(RESTABLECER, json={"token": token, "password": NUEVA})

    response = client.post(RESTABLECER, json={"token": token, "password": "Otra12345"})

    assert response.status_code == 400
    assert response.json()["code"] == "TOKEN_INVALIDO"
    assert "www-authenticate" not in response.headers
    assert hasher.verify(NUEVA, uow.usuarios.por_email[EMAIL].password_hash)


def test_token_vencido_o_inventado_400(client: TestClient) -> None:
    # Vencido e inventado son lo mismo para Valkey: la llave no existe (el TTL: integración).
    response = client.post(RESTABLECER, json={"token": "no-existe", "password": NUEVA})

    assert response.status_code == 400
    assert response.json() == {
        "detail": "El enlace de recuperación no es válido, expiró o ya se usó.",
        "code": "TOKEN_INVALIDO",
        "correlation_id": CORRELATION_ID,
    }


def test_contrasena_debil_422_sin_consumir_el_token(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
) -> None:
    token, _ = preparar_enlace(client, uow, hasher, enviador)

    response = client.post(RESTABLECER, json={"token": token, "password": "corta"})

    assert response.status_code == 422
    assert response.json()["code"] == "PASSWORD_INVALIDA"
    assert client.post(RESTABLECER, json={"token": token, "password": NUEVA}).status_code == 204


def test_cuenta_desactivada_despues_de_pedir_el_enlace_400(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
) -> None:
    token, u = preparar_enlace(client, uow, hasher, enviador)
    uow.usuarios.por_email[EMAIL] = replace(u, activo=False)

    response = client.post(RESTABLECER, json={"token": token, "password": NUEVA})

    assert response.status_code == 400
    assert uow.auditoria.registros == []


def test_valkey_caido_al_restablecer_503(
    client: TestClient, tokens_recuperacion: FakeTokensRecuperacion
) -> None:
    tokens_recuperacion.caido = True

    response = client.post(RESTABLECER, json={"token": "abc", "password": NUEVA})

    assert response.status_code == 503


def test_tokens_anteriores_dejan_de_servir(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    enviador: FakeEnviadorCorreo,
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher, Rol.TURISTA, email=EMAIL)
    client.post(RECUPERAR, json={"email": EMAIL})
    esperar_tareas(client)

    client.post(RESTABLECER, json={"token": token_del_correo(enviador), "password": NUEVA})

    assert client.get("/api/iam/perfil", headers=headers).status_code == 401
