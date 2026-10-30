import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.domain.exceptions import DocumentoNoEncontradoError
from app.domain.ports.almacen_documentos import VALIDEZ_URL, AlmacenDocumentos
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.archivo_documento import TipoArchivo
from app.domain.value_objects.enums import ResultadoAuditoria


@dataclass(frozen=True)
class EnlaceDocumento:
    url: str
    expira_en: datetime


class AbrirDocumento:
    """UC28: URL prefirmada de 5 minutos para que el Admin vea un documento (C-30).

    La consulta se audita (`DOCUMENT_VIEW`) **antes** de entregar la URL: si la bitácora no
    responde, no hay URL. A diferencia de `AUDIT_VIEW` (C-43), aquí se entrega un dato
    personal (el RUT), y cada acceso debe quedar registrado.
    """

    def __init__(
        self, uow: UnitOfWork, almacen: AlmacenDocumentos, reloj: Callable[[], datetime]
    ) -> None:
        self._uow = uow
        self._almacen = almacen
        self._reloj = reloj

    async def execute(
        self, documento_id: uuid.UUID, admin_id: uuid.UUID, ip_origen: str | None
    ) -> EnlaceDocumento:
        async with self._uow as uow:
            documento = await uow.documentos.find_by_id(documento_id)
            if documento is None:
                raise DocumentoNoEncontradoError()
            await uow.auditoria.registrar(
                accion="DOCUMENT_VIEW",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=admin_id,
                ip_origen=ip_origen,
                detalles={
                    "documento_id": str(documento_id),
                    "usuario_afectado": str(documento.usuario_id),
                    "tipo": documento.tipo_documento.value,
                },
            )
            await uow.commit()

        extension = TipoArchivo.de_tipo_contenido(documento.tipo_contenido).extension
        url = self._almacen.url_lectura(
            documento.objeto_s3,
            documento.tipo_contenido,
            f"{documento.tipo_documento.value}.{extension}",
        )
        return EnlaceDocumento(url=url, expira_en=self._reloj() + VALIDEZ_URL)
