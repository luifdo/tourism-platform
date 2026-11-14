"""UC28: aprobar y rechazar prestadores, y abrir sus documentos (C-02, C-08, C-30, C-42)."""

import uuid
from dataclasses import replace

import pytest

from app.application.use_cases.abrir_documento import AbrirDocumento
from app.application.use_cases.aprobar_prestador import AprobarPrestador, AprobarPrestadorCommand
from app.application.use_cases.rechazar_prestador import (
    DocumentoRechazado,
    RechazarPrestador,
    RechazarPrestadorCommand,
)
from app.domain.entities.documento_verificacion import EstadoVerificacion
from app.domain.entities.usuario import Usuario
from app.domain.events.prestador_aprobado import PrestadorAprobado
from app.domain.exceptions import (
    DocumentoNoEncontradoError,
    DocumentosIncompletosError,
    DocumentoYaRevisadoError,
    NoEsPrestadorError,
    UsuarioNoEncontradoError,
)
from app.domain.ports.almacen_documentos import VALIDEZ_URL
from app.domain.value_objects.enums import EstadoDocumento, ResultadoAuditoria, Rol, TipoDocumento
from tests.fakes import AHORA, FakeAlmacenDocumentos, FakeUnitOfWork, reloj_fijo

ADMIN = uuid.uuid4()
IP = "190.24.10.5"
P, A, R = EstadoDocumento.PENDIENTE, EstadoDocumento.APROBADO, EstadoDocumento.RECHAZADO
RNT, RUT = TipoDocumento.RNT, TipoDocumento.RUT


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


def sembrar_prestador(
    uow: FakeUnitOfWork, activo: bool = True, rol: Rol = Rol.PRESTADOR, **docs: EstadoDocumento
) -> Usuario:
    u = uow.usuarios.sembrar(
        Usuario(
            email=f"p.{uuid.uuid4().hex[:6]}@example.com",
            password_hash="x",
            nombre_completo="Prestador",
            rol=rol,
            activo=activo,
            habeas_data_aceptado=True,
            habeas_data_aceptado_en=AHORA,
            razon_social="Hostal Tayrona SAS",
        )
    )
    for tipo, estado in docs.items():
        uow.documentos.sembrar(u.id, TipoDocumento(tipo), estado)  # type: ignore[arg-type]
    return u


async def aprobar(uow: FakeUnitOfWork, u: Usuario | uuid.UUID):  # type: ignore[no-untyped-def]
    usuario_id = u if isinstance(u, uuid.UUID) else u.id
    return await AprobarPrestador(uow, reloj_fijo).execute(
        AprobarPrestadorCommand(admin_id=ADMIN, usuario_id=usuario_id, ip_origen=IP)  # type: ignore[arg-type]
    )


async def rechazar(uow: FakeUnitOfWork, u: Usuario, *rechazos: tuple[TipoDocumento, str]):  # type: ignore[no-untyped-def]
    return await RechazarPrestador(uow, reloj_fijo).execute(
        RechazarPrestadorCommand(
            admin_id=ADMIN,
            usuario_id=u.id,  # type: ignore[arg-type]
            documentos=[DocumentoRechazado(tipo=t, motivo=m) for t, m in rechazos],
            ip_origen=IP,
        )
    )


async def test_aprobar_marca_los_dos_audita_y_publica(uow: FakeUnitOfWork) -> None:
    u = sembrar_prestador(uow, RNT=P, RUT=P)

    resultado = await aprobar(uow, u)

    assert resultado.estado is EstadoVerificacion.APROBADO
    for d in await uow.documentos.vigentes(u.id):  # type: ignore[arg-type]
        assert (d.estado, d.revisado_por, d.revisado_en, d.motivo_rechazo) == (
            A,
            ADMIN,
            AHORA,
            None,
        )
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado, registro.usuario_id) == (
        "PROVIDER_APPROVED",
        ResultadoAuditoria.EXITO,
        ADMIN,
    )
    assert registro.detalles["usuario_afectado"] == str(u.id)
    assert len(registro.detalles["documentos"]) == 2
    assert registro.detalles["publicado"] is True
    [evento] = uow.outbox.eventos
    assert isinstance(evento, PrestadorAprobado)
    assert evento.payload() == {
        "prestador_id": str(u.id),
        "usuario_id": str(u.id),
        "aprobado_por": str(ADMIN),
        "razon_social": "Hostal Tayrona SAS",
    }
    assert uow.commits == 1


async def test_aprobar_inactivo_no_publica(uow: FakeUnitOfWork) -> None:
    u = sembrar_prestador(uow, activo=False, RNT=P, RUT=P)

    resultado = await aprobar(uow, u)

    assert resultado.estado is EstadoVerificacion.APROBADO
    assert uow.outbox.eventos == []  # sale al reactivarlo (C-42)
    assert uow.auditoria.registros[0].detalles["publicado"] is False


async def test_ya_aprobado_200_sin_efecto(uow: FakeUnitOfWork) -> None:
    u = sembrar_prestador(uow, RNT=A, RUT=A)

    resultado = await aprobar(uow, u)

    assert resultado.estado is EstadoVerificacion.APROBADO
    assert (uow.commits, uow.auditoria.registros, uow.outbox.eventos) == (0, [], [])


@pytest.mark.parametrize(
    ("docs", "error"),
    [
        ({}, DocumentosIncompletosError),
        ({"RNT": P}, DocumentosIncompletosError),
        ({"RNT": P, "RUT": R}, DocumentoYaRevisadoError),
    ],
    ids=["sin_documentos", "falta_rut", "rut_rechazado"],
)
async def test_aprobar_409(
    uow: FakeUnitOfWork, docs: dict[str, EstadoDocumento], error: type[Exception]
) -> None:
    u = sembrar_prestador(uow, **docs)

    with pytest.raises(error):
        await aprobar(uow, u)
    assert (uow.commits, uow.outbox.eventos) == (0, [])


async def test_aprobar_inexistente_o_no_prestador(uow: FakeUnitOfWork) -> None:
    with pytest.raises(UsuarioNoEncontradoError):
        await aprobar(uow, uuid.uuid4())
    turista = sembrar_prestador(uow, rol=Rol.TURISTA)
    with pytest.raises(NoEsPrestadorError):
        await aprobar(uow, turista)


async def test_rechazar_un_documento_deja_el_otro_pendiente(uow: FakeUnitOfWork) -> None:
    u = sembrar_prestador(uow, RNT=P, RUT=P)

    resultado = await rechazar(uow, u, (RUT, "El RUT está ilegible."))

    assert resultado.estado is EstadoVerificacion.RECHAZADO
    por_tipo = {d.tipo_documento: d for d in resultado.documentos}
    assert (por_tipo[RUT].estado, por_tipo[RUT].motivo_rechazo) == (R, "El RUT está ilegible.")
    assert (por_tipo[RUT].revisado_por, por_tipo[RUT].revisado_en) == (ADMIN, AHORA)
    assert por_tipo[RNT].estado is P
    [registro] = uow.auditoria.registros
    assert registro.accion == "PROVIDER_REJECTED"
    assert registro.detalles == {
        "usuario_afectado": str(u.id),
        "documentos": [
            {
                "documento_id": str(por_tipo[RUT].id),
                "tipo": "RUT",
                "motivo": "El RUT está ilegible.",
            }
        ],
    }
    assert uow.outbox.eventos == []


async def test_rechazar_los_dos(uow: FakeUnitOfWork) -> None:
    u = sembrar_prestador(uow, RNT=P, RUT=P)

    resultado = await rechazar(uow, u, (RNT, "Vencido"), (RUT, "Ilegible"))

    assert {d.estado for d in resultado.documentos} == {R}


@pytest.mark.parametrize(
    ("docs", "error"),
    [
        ({"RNT": P}, DocumentoNoEncontradoError),  # no hay RUT vigente
        ({"RUT": A}, DocumentoYaRevisadoError),
        ({"RUT": R}, DocumentoYaRevisadoError),
    ],
    ids=["sin_vigente", "aprobado", "ya_rechazado"],
)
async def test_rechazar_errores(
    uow: FakeUnitOfWork, docs: dict[str, EstadoDocumento], error: type[Exception]
) -> None:
    u = sembrar_prestador(uow, **docs)

    with pytest.raises(error):
        await rechazar(uow, u, (RUT, "x"))
    assert uow.commits == 0


async def test_abrir_audita_antes_y_entrega_la_url(uow: FakeUnitOfWork) -> None:
    u = sembrar_prestador(uow, RUT=P)
    [documento] = await uow.documentos.vigentes(u.id)  # type: ignore[arg-type]
    almacen = FakeAlmacenDocumentos()

    enlace = await AbrirDocumento(uow, almacen, reloj_fijo).execute(
        documento.id,  # type: ignore[arg-type]
        admin_id=ADMIN,
        ip_origen=IP,
    )

    assert enlace.url == (
        f"https://s3.prueba/{documento.objeto_s3}?tipo=application/pdf&nombre=RUT.pdf"
    )
    assert enlace.expira_en == AHORA + VALIDEZ_URL
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.usuario_id, registro.ip_origen) == (
        "DOCUMENT_VIEW",
        ADMIN,
        IP,
    )
    assert registro.detalles == {
        "documento_id": str(documento.id),
        "usuario_afectado": str(u.id),
        "tipo": "RUT",
    }
    assert uow.commits == 1


async def test_abrir_sin_bitacora_no_entrega_url(
    uow: FakeUnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    u = sembrar_prestador(uow, RUT=P)
    [documento] = await uow.documentos.vigentes(u.id)  # type: ignore[arg-type]

    async def falla(**_: object) -> None:
        raise ConnectionRefusedError("PostgreSQL caído")

    monkeypatch.setattr(uow.auditoria, "registrar", falla)

    with pytest.raises(ConnectionRefusedError):
        await AbrirDocumento(uow, FakeAlmacenDocumentos(), reloj_fijo).execute(
            documento.id,  # type: ignore[arg-type]
            admin_id=ADMIN,
            ip_origen=IP,
        )


async def test_abrir_inexistente(uow: FakeUnitOfWork) -> None:
    with pytest.raises(DocumentoNoEncontradoError):
        await AbrirDocumento(uow, FakeAlmacenDocumentos(), reloj_fijo).execute(
            uuid.uuid4(), admin_id=ADMIN, ip_origen=None
        )
    assert uow.auditoria.registros == []


async def test_el_png_se_sirve_como_png(uow: FakeUnitOfWork) -> None:
    u = sembrar_prestador(uow, RNT=P)
    [documento] = await uow.documentos.vigentes(u.id)  # type: ignore[arg-type]
    uow.documentos.documentos[documento.id] = replace(  # type: ignore[index]
        documento, tipo_contenido="image/png"
    )

    enlace = await AbrirDocumento(uow, FakeAlmacenDocumentos(), reloj_fijo).execute(
        documento.id,  # type: ignore[arg-type]
        admin_id=ADMIN,
        ip_origen=None,
    )

    assert enlace.url.endswith("tipo=image/png&nombre=RNT.png")
