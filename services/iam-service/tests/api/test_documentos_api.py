"""UC37 y UC28 por HTTP: carga de documentos y revisión de prestadores (C-30)."""

import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_almacen_documentos
from app.domain.entities.usuario import Usuario
from app.domain.events.prestador_aprobado import PrestadorAprobado
from app.domain.value_objects.archivo_documento import TAMANO_MAXIMO
from app.domain.value_objects.enums import EstadoDocumento, Rol, TipoDocumento
from tests.api.conftest import CORRELATION_ID, IP_CLIENTE, bearer, emitir, unico_denegado
from tests.fakes import FakeAlmacenDocumentos, FakeUnitOfWork
from tests.unit.test_documentos_dominio import PDF, PNG

MIS_DOCUMENTOS = "/api/iam/prestador/documentos"
ADMIN = "/api/iam/admin"


@pytest.fixture
def almacen(client: TestClient) -> FakeAlmacenDocumentos:
    almacen = FakeAlmacenDocumentos()
    client.app.dependency_overrides[get_almacen_documentos] = lambda: almacen  # type: ignore[attr-defined]
    return almacen


@pytest.fixture
def prestador(client: TestClient, uow: FakeUnitOfWork) -> tuple[dict[str, str], Usuario]:
    emitido, u = emitir(client, Rol.PRESTADOR)
    guardado = replace(u, email="prestador@example.com")
    uow.usuarios.por_email[guardado.email] = guardado
    return bearer(emitido.access_token), guardado


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    emitido, _ = emitir(client, Rol.ADMIN)
    return bearer(emitido.access_token)


def subir(
    client: TestClient,
    headers: dict[str, str],
    tipo: str = "RNT",
    contenido: bytes = PDF,
    nombre: str = "rnt.pdf",
    tipo_declarado: str = "application/pdf",
    **form: str,
):  # type: ignore[no-untyped-def]
    return client.post(
        MIS_DOCUMENTOS,
        data={"tipo": tipo, **form},
        files={"archivo": (nombre, contenido, tipo_declarado)},
        headers=headers,
    )


# ---------- UC37: el prestador ----------


def test_subir_201(
    client: TestClient,
    uow: FakeUnitOfWork,
    almacen: FakeAlmacenDocumentos,
    prestador: tuple[dict[str, str], Usuario],
) -> None:
    headers, u = prestador

    response = subir(client, headers)

    assert response.status_code == 201
    data = response.json()
    assert set(data) == {
        "id",
        "tipo_documento",
        "estado",
        "vigente",
        "tipo_contenido",
        "tamano_bytes",
        "motivo_rechazo",
        "fecha_subida",
        "revisado_en",
    }
    assert (data["tipo_documento"], data["estado"], data["tipo_contenido"]) == (
        "RNT",
        "Pendiente",
        "application/pdf",
    )
    assert "objeto_s3" not in response.text  # la llave interna nunca sale
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.usuario_id, registro.ip_origen) == (
        "DOCUMENT_UPLOAD",
        u.id,
        IP_CLIENTE,
    )
    assert len(almacen.objetos) == 1


def test_el_tipo_lo_da_el_contenido_y_no_lo_que_declara_el_cliente(
    client: TestClient,
    almacen: FakeAlmacenDocumentos,
    prestador: tuple[dict[str, str], Usuario],
) -> None:
    # Un PNG que dice ser PDF y se llama .pdf se guarda como PNG.
    response = subir(client, prestador[0], contenido=PNG, nombre="rnt.pdf")

    assert response.json()["tipo_contenido"] == "image/png"
    [(clave, (_, tipo))] = almacen.objetos.items()
    assert (clave.endswith(".png"), tipo) == (True, "image/png")


def test_un_ejecutable_con_nombre_pdf_es_422(
    client: TestClient,
    almacen: FakeAlmacenDocumentos,
    prestador: tuple[dict[str, str], Usuario],
) -> None:
    response = subir(client, prestador[0], contenido=b"MZ\x90\x00malicioso", nombre="rnt.pdf")

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Solo se aceptan archivos PDF, JPG o PNG.",
        "code": "TIPO_ARCHIVO_NO_PERMITIDO",
        "correlation_id": CORRELATION_ID,
    }
    assert almacen.objetos == {}


def test_mas_de_5_mb_es_413(
    client: TestClient,
    almacen: FakeAlmacenDocumentos,
    prestador: tuple[dict[str, str], Usuario],
) -> None:
    response = subir(client, prestador[0], contenido=PDF + b"0" * TAMANO_MAXIMO)

    assert response.status_code == 413
    assert response.json()["code"] == "ARCHIVO_DEMASIADO_GRANDE"
    assert almacen.objetos == {}


def test_rut_sin_razon_social_422_y_con_ella_201(
    client: TestClient,
    uow: FakeUnitOfWork,
    almacen: FakeAlmacenDocumentos,
    prestador: tuple[dict[str, str], Usuario],
) -> None:
    headers, u = prestador

    sin = subir(client, headers, tipo="RUT")
    con = subir(client, headers, tipo="RUT", razon_social="Hostal Tayrona SAS")

    assert (sin.status_code, sin.json()["code"]) == (422, "RAZON_SOCIAL_INVALIDA")
    assert con.status_code == 201
    assert uow.usuarios.por_email[u.email].razon_social == "Hostal Tayrona SAS"


@pytest.mark.parametrize(
    ("data", "files", "campo"),
    [
        ({"tipo": "CEDULA"}, {"archivo": ("x.pdf", PDF, "application/pdf")}, "tipo"),
        ({}, {"archivo": ("x.pdf", PDF, "application/pdf")}, "tipo"),
        ({"tipo": "RNT"}, None, "archivo"),
        (
            {"tipo": "RUT", "razon_social": "x" * 201},
            {"archivo": ("x.pdf", PDF, "application/pdf")},
            "razon_social",
        ),
    ],
    ids=["tipo_invalido", "sin_tipo", "sin_archivo", "razon_social_larga"],
)
def test_formulario_invalido_422(
    client: TestClient,
    almacen: FakeAlmacenDocumentos,
    prestador: tuple[dict[str, str], Usuario],
    data: dict[str, str],
    files: dict[str, tuple[str, bytes, str]] | None,
    campo: str,
) -> None:
    response = client.post(MIS_DOCUMENTOS, data=data, files=files, headers=prestador[0])

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDACION"
    assert [e["campo"] for e in response.json()["errores"]] == [campo]


def test_documento_aprobado_409(
    client: TestClient,
    uow: FakeUnitOfWork,
    almacen: FakeAlmacenDocumentos,
    prestador: tuple[dict[str, str], Usuario],
) -> None:
    headers, u = prestador
    uow.documentos.sembrar(u.id, TipoDocumento.RNT, EstadoDocumento.APROBADO)  # type: ignore[arg-type]

    response = subir(client, headers)

    assert (response.status_code, response.json()["code"]) == (409, "DOCUMENTO_APROBADO")


def test_seaweedfs_caido_503(
    client: TestClient, uow: FakeUnitOfWork, prestador: tuple[dict[str, str], Usuario]
) -> None:
    client.app.dependency_overrides[get_almacen_documentos] = lambda: FakeAlmacenDocumentos(  # type: ignore[attr-defined]
        caido=True
    )

    response = subir(client, prestador[0])

    assert (response.status_code, response.json()["code"]) == (503, "SERVICIO_NO_DISPONIBLE")
    assert uow.commits == 0


@pytest.mark.parametrize("rol", [Rol.TURISTA, Rol.ENTIDAD, Rol.ADMIN])
def test_otros_roles_no_suben_403(
    client: TestClient, uow: FakeUnitOfWork, almacen: FakeAlmacenDocumentos, rol: Rol
) -> None:
    emitido, _ = emitir(client, rol)

    response = subir(client, bearer(emitido.access_token))

    assert (response.status_code, response.json()["code"]) == (403, "ROL_INSUFICIENTE")
    unico_denegado(uow)
    assert almacen.objetos == {}


def test_sin_token_401(client: TestClient, almacen: FakeAlmacenDocumentos) -> None:
    assert subir(client, {}).status_code == 401
    assert client.get(MIS_DOCUMENTOS).status_code == 401


def test_mis_documentos(
    client: TestClient, uow: FakeUnitOfWork, prestador: tuple[dict[str, str], Usuario]
) -> None:
    headers, u = prestador
    uow.usuarios.por_email[u.email] = replace(u, razon_social="Eco SAS")
    rechazado = uow.documentos.sembrar(u.id, TipoDocumento.RUT, EstadoDocumento.RECHAZADO)  # type: ignore[arg-type]
    uow.documentos.documentos[rechazado.id] = replace(rechazado, motivo_rechazo="Ilegible")  # type: ignore[index]

    response = client.get(MIS_DOCUMENTOS, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert (data["usuario_id"], data["razon_social"], data["estado"]) == (
        str(u.id),
        "Eco SAS",
        "rechazado",
    )
    [documento] = data["documentos"]
    assert (documento["tipo_documento"], documento["motivo_rechazo"]) == ("RUT", "Ilegible")
    assert "revisado_por" not in documento  # quién revisó solo lo ve el Admin


# ---------- UC28: el Admin ----------


def con_documentos(uow: FakeUnitOfWork, u: Usuario, estado: EstadoDocumento) -> None:
    for tipo in (TipoDocumento.RNT, TipoDocumento.RUT):
        uow.documentos.sembrar(u.id, tipo, estado)  # type: ignore[arg-type]


def test_cola_de_revision(
    client: TestClient,
    uow: FakeUnitOfWork,
    admin: dict[str, str],
    prestador: tuple[dict[str, str], Usuario],
) -> None:
    _, u = prestador
    con_documentos(uow, u, EstadoDocumento.PENDIENTE)

    pendientes = client.get(f"{ADMIN}/prestadores", params={"estado": "pendiente"}, headers=admin)
    aprobados = client.get(f"{ADMIN}/prestadores", params={"estado": "aprobado"}, headers=admin)

    assert pendientes.status_code == 200
    [item] = pendientes.json()["items"]
    assert (item["usuario_id"], item["estado"], len(item["documentos"])) == (
        str(u.id),
        "pendiente",
        2,
    )
    assert "revisado_por" in item["documentos"][0]
    assert aprobados.json()["total"] == 0
    bad = client.get(f"{ADMIN}/prestadores", params={"estado": "otro"}, headers=admin)
    assert bad.status_code == 422


def test_aprobar_publica_y_audita(
    client: TestClient,
    uow: FakeUnitOfWork,
    admin: dict[str, str],
    prestador: tuple[dict[str, str], Usuario],
) -> None:
    _, u = prestador
    con_documentos(uow, u, EstadoDocumento.PENDIENTE)

    response = client.post(f"{ADMIN}/prestadores/{u.id}/aprobar", headers=admin)

    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "aprobado"
    assert {d["estado"] for d in data["documentos"]} == {"Aprobado"}
    assert all(d["revisado_por"] for d in data["documentos"])
    assert uow.auditoria.registros[0].accion == "PROVIDER_APPROVED"
    assert [type(e) for e in uow.outbox.eventos] == [PrestadorAprobado]


def test_rechazar(
    client: TestClient,
    uow: FakeUnitOfWork,
    admin: dict[str, str],
    prestador: tuple[dict[str, str], Usuario],
) -> None:
    headers, u = prestador
    con_documentos(uow, u, EstadoDocumento.PENDIENTE)

    response = client.post(
        f"{ADMIN}/prestadores/{u.id}/rechazar",
        json={"documentos": [{"tipo": "RUT", "motivo": "  Ilegible  "}]},
        headers=admin,
    )

    assert response.status_code == 200
    assert response.json()["estado"] == "rechazado"
    assert uow.auditoria.registros[0].detalles["documentos"][0]["motivo"] == "Ilegible"
    # El prestador ve el motivo y vuelve a cargar el RUT.
    [rut] = [
        d
        for d in client.get(MIS_DOCUMENTOS, headers=headers).json()["documentos"]
        if d["tipo_documento"] == "RUT"
    ]
    assert rut["motivo_rechazo"] == "Ilegible"


@pytest.mark.parametrize(
    "body",
    [
        {"documentos": []},
        {"documentos": [{"tipo": "RUT", "motivo": "   "}]},
        {"documentos": [{"tipo": "RUT", "motivo": "x" * 501}]},
        {"documentos": [{"tipo": "RUT", "motivo": "a"}, {"tipo": "RUT", "motivo": "b"}]},
        {"documentos": [{"tipo": "CEDULA", "motivo": "a"}]},
    ],
    ids=["vacio", "motivo_en_blanco", "motivo_largo", "tipo_repetido", "tipo_invalido"],
)
def test_rechazo_invalido_422(
    client: TestClient,
    uow: FakeUnitOfWork,
    admin: dict[str, str],
    prestador: tuple[dict[str, str], Usuario],
    body: dict[str, object],
) -> None:
    _, u = prestador
    con_documentos(uow, u, EstadoDocumento.PENDIENTE)

    response = client.post(f"{ADMIN}/prestadores/{u.id}/rechazar", json=body, headers=admin)

    assert (response.status_code, response.json()["code"]) == (422, "VALIDACION")
    assert uow.commits == 0


@pytest.mark.parametrize(
    ("docs", "code"),
    [(None, "DOCUMENTOS_INCOMPLETOS"), (EstadoDocumento.RECHAZADO, "DOCUMENTO_YA_REVISADO")],
)
def test_aprobar_409(
    client: TestClient,
    uow: FakeUnitOfWork,
    admin: dict[str, str],
    prestador: tuple[dict[str, str], Usuario],
    docs: EstadoDocumento | None,
    code: str,
) -> None:
    _, u = prestador
    if docs is not None:
        con_documentos(uow, u, docs)

    response = client.post(f"{ADMIN}/prestadores/{u.id}/aprobar", headers=admin)

    assert (response.status_code, response.json()["code"]) == (409, code)


def test_revisar_a_quien_no_es_prestador(
    client: TestClient, uow: FakeUnitOfWork, admin: dict[str, str]
) -> None:
    turista = uow.usuarios.sembrar(
        replace(emitir(client, Rol.TURISTA)[1], email="turista@example.com")
    )

    no_es = client.post(f"{ADMIN}/prestadores/{turista.id}/aprobar", headers=admin)
    no_existe = client.post(f"{ADMIN}/prestadores/{uuid.uuid4()}/aprobar", headers=admin)

    assert (no_es.status_code, no_es.json()["code"]) == (409, "NO_ES_PRESTADOR")
    assert (no_existe.status_code, no_existe.json()["code"]) == (404, "USUARIO_NO_ENCONTRADO")


def test_historial_y_url_del_documento(
    client: TestClient,
    uow: FakeUnitOfWork,
    almacen: FakeAlmacenDocumentos,
    admin: dict[str, str],
    prestador: tuple[dict[str, str], Usuario],
) -> None:
    headers, u = prestador
    subir(client, headers)
    subir(client, headers)  # reemplaza al primero

    historial = client.get(f"{ADMIN}/prestadores/{u.id}/documentos", headers=admin).json()
    assert [d["vigente"] for d in historial["documentos"]] == [True, False]

    vigente = historial["documentos"][0]["id"]
    response = client.get(f"{ADMIN}/documentos/{vigente}/url", headers=admin)

    assert response.status_code == 200
    assert set(response.json()) == {"url", "expira_en"}
    assert response.json()["url"].endswith("tipo=application/pdf&nombre=RNT.pdf")
    assert uow.auditoria.registros[-1].accion == "DOCUMENT_VIEW"

    no_existe = client.get(f"{ADMIN}/documentos/{uuid.uuid4()}/url", headers=admin)
    assert (no_existe.status_code, no_existe.json()["code"]) == (404, "DOCUMENTO_NO_ENCONTRADO")


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("get", "/prestadores"),
        ("get", "/prestadores/{id}/documentos"),
        ("get", "/documentos/{id}/url"),
        ("post", "/prestadores/{id}/aprobar"),
        ("post", "/prestadores/{id}/rechazar"),
    ],
)
def test_revision_solo_admin(
    client: TestClient, prestador: tuple[dict[str, str], Usuario], metodo: str, ruta: str
) -> None:
    headers, u = prestador
    url = ADMIN + ruta.format(id=u.id)

    sin_token = getattr(client, metodo)(url)
    como_prestador = getattr(client, metodo)(url, headers=headers)

    assert sin_token.status_code == 401
    assert (como_prestador.status_code, como_prestador.json()["code"]) == (403, "ROL_INSUFICIENTE")
