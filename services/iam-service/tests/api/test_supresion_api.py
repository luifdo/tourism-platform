"""Supresión de datos por HTTP (Ley 1581, C-27, C-48): orden, fallos y efectos posteriores."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.domain.events.prestador_suspendido import PrestadorSuspendido
from app.domain.value_objects.enums import EstadoDocumento, ResultadoAuditoria, Rol, TipoDocumento
from tests.api.conftest import CLAVE, IP_CLIENTE, cuenta_con_sesion, esperar_tareas
from tests.fakes import (
    AHORA,
    FakeAlmacenDocumentos,
    FakeEnviadorCorreo,
    FakePasswordHasher,
    FakeRevocacion,
    FakeUnitOfWork,
)
from tests.unit.test_documentos_dominio import PDF

PERFIL = "/api/iam/perfil"
EMAIL = "maria.perez@example.com"
ADMIN_USUARIOS = "/api/iam/admin/usuarios"


def suprimir(client: TestClient, headers: dict[str, str], password: str = CLAVE):  # type: ignore[no-untyped-def]
    return client.request("DELETE", PERFIL, json={"password": password}, headers=headers)


def test_suprime_los_datos_y_borra_los_objetos(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
    revocacion: FakeRevocacion,
) -> None:
    headers, u = cuenta_con_sesion(client, uow, hasher, Rol.PRESTADOR, razon_social="Tayrona SAS")
    otro = uuid.uuid4()
    almacen.objetos.update(
        {
            f"{u.id}/RUT/vigente.pdf": (PDF, "application/pdf"),
            f"{u.id}/RUT/reemplazado.pdf": (PDF, "application/pdf"),
            f"{otro}/RUT/ajeno.pdf": (PDF, "application/pdf"),
        }
    )
    documento = uow.documentos.sembrar(u.id, TipoDocumento.RUT, EstadoDocumento.RECHAZADO)  # type: ignore[arg-type]
    uow.documentos.documentos[documento.id].motivo_rechazo = "RUT de María Pérez, ilegible"  # type: ignore[index]

    response = suprimir(client, headers)

    assert response.status_code == 204
    final = uow.usuarios.por_email[f"suprimido+{u.id}@invalid"]
    assert EMAIL not in uow.usuarios.por_email
    assert (final.nombre_completo, final.razon_social, final.activo) == (
        "Usuario suprimido",
        None,
        False,
    )
    assert final.suprimido
    assert not hasher.verify(CLAVE, final.password_hash)
    # Solo el prefijo del usuario, con la barra: otro UUID no puede empezar igual.
    assert almacen.prefijos_borrados == [f"{u.id}/"]
    assert list(almacen.objetos) == [f"{otro}/RUT/ajeno.pdf"]
    # La fila del documento se conserva; su texto libre, no.
    conservado = uow.documentos.documentos[documento.id]  # type: ignore[index]
    assert conservado.motivo_rechazo is None
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("DATA_SUPPRESSION", ResultadoAuditoria.EXITO)
    assert (registro.usuario_id, registro.ip_origen) == (u.id, IP_CLIENTE)
    assert registro.detalles == {"rol": "Prestador", "objetos_borrados": 2}
    assert len(revocacion.revocaciones_usuario) == 2
    [evento] = uow.outbox.eventos
    assert isinstance(evento, PrestadorSuspendido)
    assert (evento.usuario_id, evento.suspendido_por) == (u.id, u.id)


def test_orden_revoca_luego_borra_y_al_final_confirma(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
    revocacion: FakeRevocacion,
) -> None:
    headers, u = cuenta_con_sesion(client, uow, hasher)
    visto: dict[str, object] = {}
    original = almacen.borrar_prefijo

    async def espiar(prefijo: str) -> int:
        visto["revocaciones"] = len(revocacion.revocaciones_usuario)
        visto["commits"] = uow.commits
        visto["activo"] = uow.usuarios.por_email[EMAIL].activo
        visto["bloqueos"] = uow.usuarios.bloqueos_admins
        return await original(prefijo)

    almacen.borrar_prefijo = espiar  # type: ignore[method-assign]

    assert suprimir(client, headers).status_code == 204

    assert visto == {"revocaciones": 1, "commits": 0, "activo": True, "bloqueos": 1}
    assert len(revocacion.revocaciones_usuario) == 2
    assert uow.commits == 1


def test_contrasena_incorrecta_401_con_su_fila_y_sin_tocar_nada(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
    revocacion: FakeRevocacion,
) -> None:
    headers, u = cuenta_con_sesion(client, uow, hasher)

    response = suprimir(client, headers, "Mala12345")

    assert response.status_code == 401
    assert response.json()["code"] == "CREDENCIALES_INVALIDAS"
    assert uow.usuarios.por_email[EMAIL].activo
    assert almacen.prefijos_borrados == []
    assert revocacion.revocaciones_usuario == []
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == (
        "DATA_SUPPRESSION",
        ResultadoAuditoria.DENEGADO,
    )
    assert registro.usuario_id == u.id


def test_valkey_caido_503_sin_borrar_nada(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
    revocacion: FakeRevocacion,
) -> None:
    headers, u = cuenta_con_sesion(client, uow, hasher)
    almacen.objetos[f"{u.id}/RUT/a.pdf"] = (PDF, "application/pdf")
    # Solo falla la revocación: la lectura del token (que también usa Valkey) sigue respondiendo.
    revocacion.al_revocar_usuario = lambda: setattr(revocacion, "caida", True)

    response = suprimir(client, headers)

    assert response.status_code == 503
    assert f"{u.id}/RUT/a.pdf" in almacen.objetos
    assert almacen.prefijos_borrados == []
    assert uow.commits == 0
    assert uow.usuarios.por_email[EMAIL].activo


def test_s3_caido_503_sin_confirmar_y_se_puede_repetir(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
    revocacion: FakeRevocacion,
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher)
    almacen.caido = True

    response = suprimir(client, headers)

    assert response.status_code == 503
    assert uow.commits == 0
    assert uow.usuarios.por_email[EMAIL].activo
    # La primera revocación ya ocurrió: el usuario inicia sesión y repite la petición (C-48).
    assert len(revocacion.revocaciones_usuario) == 1
    assert client.get(PERFIL, headers=headers).status_code == 401

    almacen.caido = False
    revocacion.revocados_desde.clear()
    assert suprimir(client, headers).status_code == 204


def test_ultimo_admin_409(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
    revocacion: FakeRevocacion,
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher, Rol.ADMIN)

    response = suprimir(client, headers)

    assert response.status_code == 409
    assert response.json()["code"] == "ULTIMO_ADMIN"
    assert almacen.prefijos_borrados == []
    assert revocacion.revocaciones_usuario == []


def test_un_admin_con_otro_activo_si_puede(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher, Rol.ADMIN)
    cuenta_con_sesion(client, uow, hasher, Rol.ADMIN, email="admin2@example.com")

    assert suprimir(client, headers).status_code == 204


def test_prestador_ya_inactivo_no_publica_otra_suspension(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher, Rol.PRESTADOR, activo=False)

    assert suprimir(client, headers).status_code == 204
    assert uow.outbox.eventos == []


def test_turista_no_publica(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher)

    assert suprimir(client, headers).status_code == 204
    assert uow.outbox.eventos == []


# ---------- Efectos posteriores ----------


@pytest.fixture
def suprimido(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
) -> uuid.UUID:
    headers, u = cuenta_con_sesion(client, uow, hasher, Rol.PRESTADOR)
    assert suprimir(client, headers).status_code == 204
    uow.auditoria.registros.clear()
    assert u.id is not None
    return u.id


@pytest.fixture
def admin(client: TestClient, uow: FakeUnitOfWork, hasher: FakePasswordHasher) -> dict[str, str]:
    headers, _ = cuenta_con_sesion(client, uow, hasher, Rol.ADMIN, email="admin@example.com")
    return headers


def test_el_token_anterior_deja_de_servir(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
) -> None:
    headers, _ = cuenta_con_sesion(client, uow, hasher)

    suprimir(client, headers)

    assert client.get(PERFIL, headers=headers).status_code == 401


def test_login_falla_como_credenciales_invalidas(
    client: TestClient, suprimido: uuid.UUID, uow: FakeUnitOfWork
) -> None:
    for email in (EMAIL, f"suprimido+{suprimido}@invalid"):
        response = client.post("/api/iam/login", json={"email": email, "password": CLAVE})

        assert response.status_code == 401
        assert response.json()["code"] == "CREDENCIALES_INVALIDAS"


def test_recuperar_no_envia_nada(
    client: TestClient, suprimido: uuid.UUID, enviador: FakeEnviadorCorreo
) -> None:
    for email in (EMAIL, f"suprimido+{suprimido}@invalid"):
        assert client.post("/api/iam/auth/recuperar", json={"email": email}).status_code == 202
    esperar_tareas(client)

    assert enviador.enviados == []


def test_contacto_interno_404(client: TestClient, suprimido: uuid.UUID) -> None:
    response = client.get(f"/internal/usuarios/{suprimido}/contacto")

    assert response.status_code == 404
    assert response.json()["code"] == "USUARIO_NO_ENCONTRADO"


def test_url_del_documento_404_sin_auditar(
    client: TestClient, uow: FakeUnitOfWork, suprimido: uuid.UUID, admin: dict[str, str]
) -> None:
    documento = uow.documentos.sembrar(suprimido, TipoDocumento.RUT, EstadoDocumento.APROBADO)

    response = client.get(f"/api/iam/admin/documentos/{documento.id}/url", headers=admin)

    assert response.status_code == 404
    assert response.json()["code"] == "DOCUMENTO_NO_ENCONTRADO"
    assert uow.auditoria.registros == []


def test_cola_de_prestadores_la_excluye(
    client: TestClient, suprimido: uuid.UUID, admin: dict[str, str]
) -> None:
    data = client.get("/api/iam/admin/prestadores", headers=admin).json()

    assert data["total"] == 0
    assert data["items"] == []


def test_listado_de_admin_la_muestra_como_usuario_suprimido(
    client: TestClient, suprimido: uuid.UUID, admin: dict[str, str]
) -> None:
    data = client.get(ADMIN_USUARIOS, params={"activo": False}, headers=admin).json()

    [cuenta] = data["items"]
    assert (cuenta["id"], cuenta["nombre_completo"], cuenta["email"]) == (
        str(suprimido),
        "Usuario suprimido",
        f"suprimido+{suprimido}@invalid",
    )


@pytest.mark.parametrize(
    ("ruta", "cuerpo"),
    [("estado", {"activo": True}), ("estado", {"activo": False}), ("rol", {"rol": "Turista"})],
)
def test_admin_no_puede_reactivar_ni_cambiar_el_rol(
    client: TestClient,
    uow: FakeUnitOfWork,
    suprimido: uuid.UUID,
    admin: dict[str, str],
    ruta: str,
    cuerpo: dict[str, object],
) -> None:
    response = client.patch(f"{ADMIN_USUARIOS}/{suprimido}/{ruta}", json=cuerpo, headers=admin)

    assert response.status_code == 409
    assert response.json()["code"] == "CUENTA_SUPRIMIDA"
    assert uow.auditoria.registros == []
    # Solo la suspensión de la propia supresión.
    assert len(uow.outbox.eventos) == 1


def test_admin_no_puede_aprobar_ni_rechazar(
    client: TestClient, suprimido: uuid.UUID, admin: dict[str, str]
) -> None:
    aprobar = client.post(f"/api/iam/admin/prestadores/{suprimido}/aprobar", headers=admin)
    rechazar = client.post(
        f"/api/iam/admin/prestadores/{suprimido}/rechazar",
        json={"documentos": [{"tipo": "RUT", "motivo": "x"}]},
        headers=admin,
    )

    assert (aprobar.status_code, rechazar.status_code) == (409, 409)
    assert aprobar.json()["code"] == "CUENTA_SUPRIMIDA"


def test_carga_que_termina_despues_de_la_supresion_borra_el_objeto(
    client: TestClient,
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
) -> None:
    headers, u = cuenta_con_sesion(client, uow, hasher, Rol.PRESTADOR)

    async def suprimir_mientras_sube() -> None:
        assert u.id is not None
        await uow.usuarios.suprimir_datos(u.id, "x", AHORA)

    almacen.al_guardar = suprimir_mientras_sube

    response = client.post(
        "/api/iam/prestador/documentos",
        data={"tipo": "RNT"},
        files={"archivo": ("rnt.pdf", PDF, "application/pdf")},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "CUENTA_SUPRIMIDA"
    assert almacen.objetos == {}
    assert uow.documentos.documentos == {}
