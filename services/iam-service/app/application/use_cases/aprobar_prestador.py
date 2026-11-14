import uuid
from dataclasses import dataclass

from app.application.use_cases.consultar_verificacion import Verificacion
from app.application.use_cases.revision_prestador import RevisionPrestador, verificacion
from app.domain.entities.documento_verificacion import TIPOS_REQUERIDOS
from app.domain.events.prestador_aprobado import PrestadorAprobado
from app.domain.exceptions import DocumentosIncompletosError, DocumentoYaRevisadoError
from app.domain.value_objects.enums import EstadoDocumento, ResultadoAuditoria


@dataclass(frozen=True)
class AprobarPrestadorCommand:
    admin_id: uuid.UUID
    usuario_id: uuid.UUID
    ip_origen: str | None


class AprobarPrestador(RevisionPrestador):
    """UC28: el Admin aprueba el RNT y el RUT vigentes de un prestador (`PROVIDER_APPROVED`).

    * Exige los dos documentos vigentes, ninguno rechazado (409).
    * Ya aprobado: 200 sin auditar ni publicar.
    * En una transacción: los documentos pendientes pasan a Aprobado (con quién y cuándo,
      C-02), la fila de la bitácora y, si la cuenta está activa, `prestador.aprobado` en el
      outbox. Si está inactiva, el evento sale al reactivarla (C-42).
    """

    async def execute(self, cmd: AprobarPrestadorCommand) -> Verificacion:
        async with self._uow as uow:
            prestador = await self._prestador_bloqueado(uow, cmd.usuario_id)
            vigentes = await uow.documentos.vigentes(cmd.usuario_id)
            if {d.tipo_documento for d in vigentes} != TIPOS_REQUERIDOS:
                raise DocumentosIncompletosError()
            if any(d.estado is EstadoDocumento.RECHAZADO for d in vigentes):
                raise DocumentoYaRevisadoError()
            pendientes = [d for d in vigentes if d.estado is EstadoDocumento.PENDIENTE]
            if not pendientes:
                return verificacion(prestador, vigentes)

            ahora = self._reloj()
            aprobados = {
                d.id: await uow.documentos.marcar_revisado(
                    d.id,  # type: ignore[arg-type]
                    EstadoDocumento.APROBADO,
                    cmd.admin_id,
                    ahora,
                    None,
                )
                for d in pendientes
            }
            vigentes = [aprobados.get(d.id, d) for d in vigentes]
            await uow.auditoria.registrar(
                accion="PROVIDER_APPROVED",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=cmd.admin_id,
                ip_origen=cmd.ip_origen,
                detalles={
                    "usuario_afectado": str(cmd.usuario_id),
                    "documentos": sorted(str(d.id) for d in vigentes),
                    "publicado": prestador.activo,
                },
            )
            if prestador.activo:
                await uow.outbox.agregar(
                    PrestadorAprobado(
                        ocurrido_en=ahora,
                        usuario_id=cmd.usuario_id,
                        aprobado_por=cmd.admin_id,
                        razon_social=prestador.razon_social,
                    )
                )
            await uow.commit()
        return verificacion(prestador, vigentes)
