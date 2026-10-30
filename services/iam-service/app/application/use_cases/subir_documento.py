import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.entities.documento_verificacion import DocumentoVerificacion
from app.domain.exceptions import (
    DocumentoAprobadoError,
    NoEsPrestadorError,
    RazonSocialInvalidaError,
    UsuarioNoEncontradoError,
)
from app.domain.ports.almacen_documentos import AlmacenDocumentos
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.archivo_documento import ArchivoDocumento
from app.domain.value_objects.enums import EstadoDocumento, ResultadoAuditoria, Rol, TipoDocumento

logger = logging.getLogger(__name__)

RAZON_SOCIAL_MIN = 2
RAZON_SOCIAL_MAX = 200


@dataclass(frozen=True)
class SubirDocumentoCommand:
    usuario_id: uuid.UUID
    tipo: TipoDocumento
    contenido: bytes = field(repr=False)
    razon_social: str | None
    ip_origen: str | None


class SubirDocumento:
    """UC37: el prestador carga su RNT o su RUT (RF-12, C-30).

    1. Valida el archivo por su firma de bytes y su tamaño, y la razón social con el RUT.
    2. Si el vigente de ese tipo ya está aprobado: 409, sin subir nada.
    3. Sube el objeto a SeaweedFS (si no responde, 503).
    4. En una transacción, con la cuenta bloqueada (contra cargas o revisiones simultáneas):
       retira el vigente anterior, guarda el nuevo como Pendiente, guarda la razón social y
       audita `DOCUMENT_UPLOAD`. Si la base falla aquí, el objeto queda huérfano en el bucket
       (con una llave que no se puede adivinar) y queda en el log.
    """

    def __init__(
        self, uow: UnitOfWork, almacen: AlmacenDocumentos, reloj: Callable[[], datetime]
    ) -> None:
        self._uow = uow
        self._almacen = almacen
        self._reloj = reloj

    async def execute(self, cmd: SubirDocumentoCommand) -> DocumentoVerificacion:
        archivo = ArchivoDocumento.validar(cmd.contenido)
        razon_social = _razon_social(cmd)
        async with self._uow as uow:
            _rechazar_si_aprobado(await uow.documentos.vigentes(cmd.usuario_id), cmd.tipo)

        clave = f"{cmd.usuario_id}/{cmd.tipo.value}/{uuid.uuid4()}.{archivo.tipo.extension}"
        await self._almacen.guardar(clave, archivo.contenido, archivo.tipo.tipo_contenido)

        try:
            return await self._registrar(cmd, archivo, clave, razon_social)
        except Exception:
            logger.error("Documento subido sin registrar en la base; objeto huérfano: %s", clave)
            raise

    async def _registrar(
        self,
        cmd: SubirDocumentoCommand,
        archivo: ArchivoDocumento,
        clave: str,
        razon_social: str | None,
    ) -> DocumentoVerificacion:
        async with self._uow as uow:
            prestador = await uow.usuarios.find_by_id_para_actualizar(cmd.usuario_id)
            if prestador is None:
                raise UsuarioNoEncontradoError()
            if prestador.rol is not Rol.PRESTADOR:
                raise NoEsPrestadorError()
            vigentes = await uow.documentos.vigentes(cmd.usuario_id)
            _rechazar_si_aprobado(vigentes, cmd.tipo)
            anterior = next((d for d in vigentes if d.tipo_documento is cmd.tipo), None)

            await uow.documentos.retirar_vigente(cmd.usuario_id, cmd.tipo)
            documento = await uow.documentos.agregar(
                DocumentoVerificacion(
                    usuario_id=cmd.usuario_id,
                    tipo_documento=cmd.tipo,
                    objeto_s3=clave,
                    tipo_contenido=archivo.tipo.tipo_contenido,
                    tamano_bytes=archivo.tamano_bytes,
                )
            )
            if razon_social is not None:
                await uow.usuarios.actualizar_razon_social(cmd.usuario_id, razon_social)
            await uow.auditoria.registrar(
                accion="DOCUMENT_UPLOAD",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=cmd.usuario_id,
                ip_origen=cmd.ip_origen,
                detalles={
                    "documento_id": str(documento.id),
                    "tipo": cmd.tipo.value,
                    "tipo_contenido": archivo.tipo.tipo_contenido,
                    "tamano_bytes": archivo.tamano_bytes,
                    "reemplaza": str(anterior.id) if anterior else None,
                },
            )
            await uow.commit()
        return documento


def _razon_social(cmd: SubirDocumentoCommand) -> str | None:
    """Obligatoria con el RUT (C-07); con el RNT no se usa."""
    if cmd.tipo is not TipoDocumento.RUT:
        return None
    razon_social = (cmd.razon_social or "").strip()
    if not RAZON_SOCIAL_MIN <= len(razon_social) <= RAZON_SOCIAL_MAX:
        raise RazonSocialInvalidaError()
    return razon_social


def _rechazar_si_aprobado(vigentes: list[DocumentoVerificacion], tipo: TipoDocumento) -> None:
    if any(d.tipo_documento is tipo and d.estado is EstadoDocumento.APROBADO for d in vigentes):
        raise DocumentoAprobadoError()
