"""Archivo por firma de bytes y tamaño (C-30), y estado derivado del prestador (UC28)."""

import uuid

import pytest

from app.domain.entities.documento_verificacion import (
    DocumentoVerificacion,
    EstadoVerificacion,
    estado_verificacion,
)
from app.domain.exceptions import ArchivoDemasiadoGrandeError, TipoArchivoNoPermitidoError
from app.domain.value_objects.archivo_documento import TAMANO_MAXIMO, ArchivoDocumento, TipoArchivo
from app.domain.value_objects.enums import EstadoDocumento, TipoDocumento

PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n"
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


@pytest.mark.parametrize(
    ("contenido", "tipo", "tipo_contenido", "extension"),
    [
        (PDF, TipoArchivo.PDF, "application/pdf", "pdf"),
        (JPEG, TipoArchivo.JPEG, "image/jpeg", "jpg"),
        (PNG, TipoArchivo.PNG, "image/png", "png"),
    ],
)
def test_reconoce_por_la_firma(
    contenido: bytes, tipo: TipoArchivo, tipo_contenido: str, extension: str
) -> None:
    archivo = ArchivoDocumento.validar(contenido)

    assert archivo.tipo is tipo
    assert (archivo.tipo.tipo_contenido, archivo.tipo.extension) == (tipo_contenido, extension)
    assert archivo.tamano_bytes == len(contenido)


@pytest.mark.parametrize(
    "contenido",
    [
        b"",
        b"GIF89a\x01\x00",
        b"<html><script>alert(1)</script>",
        b"MZ\x90\x00",  # ejecutable de Windows
        b"PK\x03\x04",  # zip (o un .docx)
        b" %PDF-1.7",  # la firma debe estar al inicio
    ],
    ids=["vacio", "gif", "html", "exe", "zip", "firma_desplazada"],
)
def test_rechaza_lo_que_no_es_pdf_jpg_ni_png(contenido: bytes) -> None:
    with pytest.raises(TipoArchivoNoPermitidoError):
        ArchivoDocumento.validar(contenido)


def test_cinco_mb_exactos_si_y_un_byte_mas_no() -> None:
    relleno = PDF + b"0" * (TAMANO_MAXIMO - len(PDF))

    assert ArchivoDocumento.validar(relleno).tamano_bytes == TAMANO_MAXIMO
    with pytest.raises(ArchivoDemasiadoGrandeError):
        ArchivoDocumento.validar(relleno + b"0")


def doc(tipo: TipoDocumento, estado: EstadoDocumento) -> DocumentoVerificacion:
    return DocumentoVerificacion(
        usuario_id=uuid.uuid4(),
        tipo_documento=tipo,
        objeto_s3="x",
        tipo_contenido="application/pdf",
        tamano_bytes=1,
        estado=estado,
    )


P, A, R = EstadoDocumento.PENDIENTE, EstadoDocumento.APROBADO, EstadoDocumento.RECHAZADO
RNT, RUT = TipoDocumento.RNT, TipoDocumento.RUT


@pytest.mark.parametrize(
    ("vigentes", "esperado"),
    [
        ([], EstadoVerificacion.INCOMPLETO),
        ([(RNT, P)], EstadoVerificacion.INCOMPLETO),
        ([(RUT, A)], EstadoVerificacion.INCOMPLETO),
        ([(RNT, P), (RUT, P)], EstadoVerificacion.PENDIENTE),
        ([(RNT, A), (RUT, P)], EstadoVerificacion.PENDIENTE),
        ([(RNT, A), (RUT, A)], EstadoVerificacion.APROBADO),
        ([(RNT, R), (RUT, P)], EstadoVerificacion.RECHAZADO),
        ([(RUT, R)], EstadoVerificacion.RECHAZADO),  # rechazado antes que incompleto
    ],
)
def test_estado_verificacion(
    vigentes: list[tuple[TipoDocumento, EstadoDocumento]], esperado: EstadoVerificacion
) -> None:
    assert estado_verificacion([doc(t, e) for t, e in vigentes]) is esperado
