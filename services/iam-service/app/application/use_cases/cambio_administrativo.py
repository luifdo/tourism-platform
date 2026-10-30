import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

from app.domain.entities.documento_verificacion import EstadoVerificacion, estado_verificacion
from app.domain.entities.usuario import Usuario
from app.domain.events.prestador_aprobado import PrestadorAprobado
from app.domain.events.prestador_suspendido import PrestadorSuspendido
from app.domain.exceptions import (
    AutogestionNoPermitidaError,
    ServicioNoDisponibleError,
    UltimoAdminError,
    UsuarioNoEncontradoError,
)
from app.domain.ports.revocacion_tokens import RevocacionTokens
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import ResultadoAuditoria, Rol

logger = logging.getLogger(__name__)

# El motivo va a la bitácora recortado; nunca al bus (C-41).
MOTIVO_MAX = 500


@dataclass(frozen=True)
class CambioAdministrativoCommand:
    admin_id: uuid.UUID
    usuario_id: uuid.UUID
    motivo: str | None
    ip_origen: str | None


class CambioAdministrativo:
    """Pasos comunes de los cambios de UC27 (rol y estado de una cuenta).

    1. Bloquea los Admins activos y luego la cuenta afectada (C-29).
    2. Sin efecto (mismo rol y mismo estado): devuelve la cuenta sin auditar, revocar ni
       publicar.
    3. Reglas: no sobre la propia cuenta; no dejar la plataforma sin Admins activos.
    4. En una sola transacción: el cambio, su fila en la bitácora y, en el outbox,
       `prestador.suspendido` si el prestador deja de estar visible (C-17), o
       `prestador.aprobado` si vuelve a estarlo con sus documentos aprobados (C-42).
    5. Si cambió el rol o se desactivó, revoca los tokens del usuario antes del commit (si
       Valkey no responde, 503 y nada se confirma) y otra vez después (C-21).
    """

    accion: ClassVar[str]

    def __init__(
        self, uow: UnitOfWork, revocacion: RevocacionTokens, reloj: Callable[[], datetime]
    ) -> None:
        self._uow = uow
        self._revocacion = revocacion
        self._reloj = reloj

    async def _aplicar(
        self, cmd: CambioAdministrativoCommand, nuevo: Callable[[Usuario], tuple[Rol, bool]]
    ) -> Usuario:
        async with self._uow as uow:
            admins_activos = await uow.usuarios.bloquear_admins_activos()
            objetivo = await uow.usuarios.find_by_id_para_actualizar(cmd.usuario_id)
            if objetivo is None or objetivo.id is None:
                raise UsuarioNoEncontradoError()
            rol, activo = nuevo(objetivo)
            if (rol, activo) == (objetivo.rol, objetivo.activo):
                return objetivo
            if objetivo.id == cmd.admin_id:
                raise AutogestionNoPermitidaError()
            era_admin = objetivo.rol is Rol.ADMIN and objetivo.activo
            if era_admin and not (rol is Rol.ADMIN and activo) and admins_activos <= 1:
                raise UltimoAdminError()

            ahora = self._reloj()
            actualizado = await uow.usuarios.actualizar_rol_y_estado(objetivo.id, rol, activo)
            await uow.auditoria.registrar(
                accion=self.accion,
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=cmd.admin_id,
                ip_origen=cmd.ip_origen,
                detalles=_detalles(objetivo, actualizado, cmd.motivo),
            )
            era_prestador_visible = objetivo.rol is Rol.PRESTADOR and objetivo.activo
            es_prestador_visible = rol is Rol.PRESTADOR and activo
            if era_prestador_visible and not es_prestador_visible:
                await uow.outbox.agregar(
                    PrestadorSuspendido(
                        ocurrido_en=ahora, usuario_id=objetivo.id, suspendido_por=cmd.admin_id
                    )
                )
            elif es_prestador_visible and not era_prestador_visible:
                vigentes = await uow.documentos.vigentes(objetivo.id)
                if estado_verificacion(vigentes) is EstadoVerificacion.APROBADO:
                    await uow.outbox.agregar(
                        PrestadorAprobado(
                            ocurrido_en=ahora,
                            usuario_id=objetivo.id,
                            aprobado_por=cmd.admin_id,
                            razon_social=objetivo.razon_social,
                        )
                    )
            revocar = rol is not objetivo.rol or (objetivo.activo and not activo)
            if revocar:
                await self._revocacion.revocar_usuario(objetivo.id, ahora)
            await uow.commit()

        if revocar:
            await self._revocar_tras_commit(objetivo.id)
        return actualizado

    async def _revocar_tras_commit(self, usuario_id: uuid.UUID) -> None:
        # Cierra la ventana entre la primera revocación y el commit: un login en el segundo
        # siguiente leía aún el rol o el estado viejos y su token quedaba fuera de la marca.
        try:
            await self._revocacion.revocar_usuario(usuario_id, self._reloj())
        except ServicioNoDisponibleError:
            logger.error(
                "No se pudo repetir la revocación por usuario tras el commit", exc_info=True
            )


def _detalles(antes: Usuario, despues: Usuario, motivo: str | None) -> dict[str, Any]:
    cambios_antes: dict[str, Any] = {}
    cambios_despues: dict[str, Any] = {}
    if antes.rol is not despues.rol:
        cambios_antes["rol"], cambios_despues["rol"] = antes.rol.value, despues.rol.value
    if antes.activo != despues.activo:
        cambios_antes["activo"], cambios_despues["activo"] = antes.activo, despues.activo
    recortado = motivo.strip()[:MOTIVO_MAX] if motivo else ""
    return {
        "usuario_afectado": str(antes.id),
        "antes": cambios_antes,
        "despues": cambios_despues,
        "motivo": recortado or None,
    }
