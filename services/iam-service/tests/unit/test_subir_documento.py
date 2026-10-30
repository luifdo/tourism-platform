"""UC37: carga de RNT y RUT (C-07, C-30)."""

import uuid
from dataclasses import replace

import pytest

from app.application.use_cases.subir_documento import SubirDocumento, SubirDocumentoCommand
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import (
    ArchivoDemasiadoGrandeError,
    DocumentoAprobadoError,
    NoEsPrestadorError,
    RazonSocialInvalidaError,
    ServicioNoDisponibleError,
    TipoArchivoNoPermitidoError,
)
from app.domain.value_objects.archivo_documento import TAMANO_MAXIMO
from app.domain.value_objects.enums import EstadoDocumento, ResultadoAuditoria, Rol, TipoDocumento
from tests.fakes import AHORA, FakeAlmacenDocumentos, FakeUnitOfWork, reloj_fijo
from tests.unit.test_documentos_dominio import PDF, PNG

IP = "190.24.10.5"


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def almacen() -> FakeAlmacenDocumentos:
    return FakeAlmacenDocumentos()


@pytest.fixture
def prestador(uow: FakeUnitOfWork) -> Usuario:
    return uow.usuarios.sembrar(
        Usuario(
            email="prestador@example.com",
            password_hash="x",
            nombre_completo="Prestador",
            rol=Rol.PRESTADOR,
            habeas_data_aceptado=True,
            habeas_data_aceptado_en=AHORA,
        )
    )


def subir(uow: FakeUnitOfWork, almacen: FakeAlmacenDocumentos) -> SubirDocumento:
    return SubirDocumento(uow=uow, almacen=almacen, reloj=reloj_fijo)


def cmd(
    prestador: Usuario,
    tipo: TipoDocumento = TipoDocumento.RNT,
    contenido: bytes = PDF,
    razon_social: str | None = None,
) -> SubirDocumentoCommand:
    assert prestador.id is not None
    return SubirDocumentoCommand(
        usuario_id=prestador.id,
        tipo=tipo,
        contenido=contenido,
        razon_social=razon_social,
        ip_origen=IP,
    )


async def test_rnt_se_guarda_pendiente_con_su_objeto_y_su_auditoria(
    uow: FakeUnitOfWork, almacen: FakeAlmacenDocumentos, prestador: Usuario
) -> None:
    documento = await subir(uow, almacen).execute(cmd(prestador))

    assert (documento.estado, documento.vigente, documento.tipo_documento) == (
        EstadoDocumento.PENDIENTE,
        True,
        TipoDocumento.RNT,
    )
    assert (documento.tipo_contenido, documento.tamano_bytes) == ("application/pdf", len(PDF))
    # La llave no se puede adivinar y nunca lleva el nombre del archivo del cliente.
    assert documento.objeto_s3.startswith(f"{prestador.id}/RNT/")
    assert documento.objeto_s3.endswith(".pdf")
    assert almacen.objetos[documento.objeto_s3] == (PDF, "application/pdf")
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("DOCUMENT_UPLOAD", ResultadoAuditoria.EXITO)
    assert (registro.usuario_id, registro.ip_origen) == (prestador.id, IP)
    assert registro.detalles == {
        "documento_id": str(documento.id),
        "tipo": "RNT",
        "tipo_contenido": "application/pdf",
        "tamano_bytes": len(PDF),
        "reemplaza": None,
    }
    assert uow.commits == 1


async def test_rut_guarda_la_razon_social(
    uow: FakeUnitOfWork, almacen: FakeAlmacenDocumentos, prestador: Usuario
) -> None:
    await subir(uow, almacen).execute(
        cmd(prestador, TipoDocumento.RUT, PNG, razon_social="  Hostal Tayrona SAS  ")
    )

    assert (await uow.usuarios.find_by_id(prestador.id)).razon_social == "Hostal Tayrona SAS"  # type: ignore[arg-type, union-attr]


@pytest.mark.parametrize("razon_social", [None, "", "  ", "x", "a" * 201])
async def test_rut_sin_razon_social_valida(
    uow: FakeUnitOfWork,
    almacen: FakeAlmacenDocumentos,
    prestador: Usuario,
    razon_social: str | None,
) -> None:
    with pytest.raises(RazonSocialInvalidaError):
        await subir(uow, almacen).execute(
            cmd(prestador, TipoDocumento.RUT, razon_social=razon_social)
        )
    assert almacen.objetos == {}


async def test_con_el_rnt_la_razon_social_no_se_usa(
    uow: FakeUnitOfWork, almacen: FakeAlmacenDocumentos, prestador: Usuario
) -> None:
    await subir(uow, almacen).execute(cmd(prestador, razon_social="Otra SAS"))

    assert (await uow.usuarios.find_by_id(prestador.id)).razon_social is None  # type: ignore[arg-type, union-attr]


@pytest.mark.parametrize("estado", [EstadoDocumento.PENDIENTE, EstadoDocumento.RECHAZADO])
async def test_reemplaza_al_pendiente_o_al_rechazado_y_lo_conserva(
    uow: FakeUnitOfWork, almacen: FakeAlmacenDocumentos, prestador: Usuario, estado: EstadoDocumento
) -> None:
    anterior = uow.documentos.sembrar(prestador.id, TipoDocumento.RNT, estado)  # type: ignore[arg-type]

    nuevo = await subir(uow, almacen).execute(cmd(prestador))

    [vigente] = await uow.documentos.vigentes(prestador.id)  # type: ignore[arg-type]
    assert vigente.id == nuevo.id
    assert uow.documentos.documentos[anterior.id].vigente is False  # type: ignore[index]
    assert len(await uow.documentos.historial(prestador.id)) == 2  # type: ignore[arg-type]
    assert uow.auditoria.registros[0].detalles["reemplaza"] == str(anterior.id)


async def test_documento_aprobado_409_sin_subir_nada(
    uow: FakeUnitOfWork, almacen: FakeAlmacenDocumentos, prestador: Usuario
) -> None:
    uow.documentos.sembrar(prestador.id, TipoDocumento.RNT, EstadoDocumento.APROBADO)  # type: ignore[arg-type]

    with pytest.raises(DocumentoAprobadoError):
        await subir(uow, almacen).execute(cmd(prestador))

    assert almacen.objetos == {}
    assert uow.commits == 0


async def test_el_otro_tipo_aprobado_no_impide_cargar(
    uow: FakeUnitOfWork, almacen: FakeAlmacenDocumentos, prestador: Usuario
) -> None:
    uow.documentos.sembrar(prestador.id, TipoDocumento.RUT, EstadoDocumento.APROBADO)  # type: ignore[arg-type]

    documento = await subir(uow, almacen).execute(cmd(prestador))

    assert documento.tipo_documento is TipoDocumento.RNT


@pytest.mark.parametrize(
    ("contenido", "error"),
    [
        (b"GIF89a", TipoArchivoNoPermitidoError),
        (PDF + b"0" * TAMANO_MAXIMO, ArchivoDemasiadoGrandeError),
    ],
    ids=["tipo", "tamano"],
)
async def test_archivo_invalido_no_sube_ni_registra(
    uow: FakeUnitOfWork,
    almacen: FakeAlmacenDocumentos,
    prestador: Usuario,
    contenido: bytes,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        await subir(uow, almacen).execute(cmd(prestador, contenido=contenido))
    assert (almacen.objetos, uow.entradas) == ({}, 0)


async def test_seaweedfs_caido_503_sin_registrar(uow: FakeUnitOfWork, prestador: Usuario) -> None:
    with pytest.raises(ServicioNoDisponibleError):
        await subir(uow, FakeAlmacenDocumentos(caido=True)).execute(cmd(prestador))
    assert uow.commits == 0
    assert uow.documentos.documentos == {}


async def test_si_ya_no_es_prestador_al_registrar(
    uow: FakeUnitOfWork, almacen: FakeAlmacenDocumentos, prestador: Usuario
) -> None:
    # El Admin le cambió el rol entre la carga y el registro (su token aún no expiró).
    uow.usuarios.por_email[prestador.email] = replace(prestador, rol=Rol.TURISTA)

    with pytest.raises(NoEsPrestadorError):
        await subir(uow, almacen).execute(cmd(prestador))
    assert uow.commits == 0


async def test_cada_carga_usa_una_llave_distinta(
    uow: FakeUnitOfWork, almacen: FakeAlmacenDocumentos, prestador: Usuario
) -> None:
    primero = await subir(uow, almacen).execute(cmd(prestador))
    segundo = await subir(uow, almacen).execute(cmd(prestador))

    assert primero.objeto_s3 != segundo.objeto_s3
    assert len(almacen.objetos) == 2
    assert uuid.UUID(segundo.objeto_s3.split("/")[-1].removesuffix(".pdf"))
