import uuid
from dataclasses import dataclass

from app.application.use_cases.consultar_verificacion import Verificacion
from app.application.use_cases.revision_prestador import RevisionPrestador, verificacion
from app.domain.exceptions import DocumentoNoEncontradoError, DocumentoYaRevisadoError
from app.domain.value_objects.enums import EstadoDocumento, ResultadoAuditoria, TipoDocumento


@dataclass(frozen=True)
class DocumentoRechazado:
    tipo: TipoDocumento
    motivo: str


@dataclass(frozen=True)
class RechazarPrestadorCommand:
    admin_id: uuid.UUID
    usuario_id: uuid.UUID
    documentos: list[DocumentoRechazado]
    ip_origen: str | None


class RechazarPrestador(RevisionPrestador):
    """UC28: el Admin rechaza uno o los dos documentos vigentes (`PROVIDER_REJECTED`).

    Solo los pendientes (409 si ya se revisaron: a un prestador aprobado se le suspende con
    UC27). El motivo queda en el documento, para que el prestador sepa qué corregir (C-02),
    y en la bitácora. No publica ningún evento: catalog nunca supo de este prestador.
    """

    async def execute(self, cmd: RechazarPrestadorCommand) -> Verificacion:
        async with self._uow as uow:
            prestador = await self._prestador_bloqueado(uow, cmd.usuario_id)
            vigentes = {d.tipo_documento: d for d in await uow.documentos.vigentes(cmd.usuario_id)}
            for rechazo in cmd.documentos:
                documento = vigentes.get(rechazo.tipo)
                if documento is None:
                    raise DocumentoNoEncontradoError()
                if documento.estado is not EstadoDocumento.PENDIENTE:
                    raise DocumentoYaRevisadoError()

            ahora = self._reloj()
            for rechazo in cmd.documentos:
                vigentes[rechazo.tipo] = await uow.documentos.marcar_revisado(
                    vigentes[rechazo.tipo].id,  # type: ignore[arg-type]
                    EstadoDocumento.RECHAZADO,
                    cmd.admin_id,
                    ahora,
                    rechazo.motivo,
                )
            await uow.auditoria.registrar(
                accion="PROVIDER_REJECTED",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=cmd.admin_id,
                ip_origen=cmd.ip_origen,
                detalles={
                    "usuario_afectado": str(cmd.usuario_id),
                    "documentos": [
                        {
                            "documento_id": str(vigentes[r.tipo].id),
                            "tipo": r.tipo.value,
                            "motivo": r.motivo,
                        }
                        for r in cmd.documentos
                    ],
                },
            )
            await uow.commit()
        return verificacion(prestador, list(vigentes.values()))
