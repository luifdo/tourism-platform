import asyncio
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.application.use_cases.revocacion_doble import RevocacionDoble
from app.domain.entities.usuario import Usuario
from app.domain.events.prestador_suspendido import PrestadorSuspendido
from app.domain.exceptions import CredencialesInvalidasError, UltimoAdminError
from app.domain.ports.almacen_documentos import AlmacenDocumentos
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.revocacion_tokens import RevocacionTokens
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import ResultadoAuditoria, Rol


@dataclass(frozen=True)
class SuprimirDatosCommand:
    usuario_id: uuid.UUID
    password: str = field(repr=False)
    ip_origen: str | None


class SuprimirDatos:
    """Ley 1581: supresión de los datos personales por anonimización (C-27, C-48).

    Pide la contraseña porque es irreversible: un token robado no debe bastar. Luego, con los
    Admins activos y la cuenta bloqueados:

    1. Si es el último Admin activo, 409.
    2. Primera revocación; si Valkey falla, 503 sin haber borrado nada.
    3. Borra en SeaweedFS todo el prefijo `{usuario_id}/`, incluidos los documentos no vigentes
       y los huérfanos. Si falla, 503.
    4. En la transacción: datos neutros, motivos de rechazo vacíos, `DATA_SUPPRESSION` y
       `prestador.suspendido` si era un Prestador visible.
    5. Commit y segunda revocación.

    El orden es deliberado: lo único irreversible fuera de la transacción es el paso 3, así que
    solo corre cuando Valkey respondió. Si el paso 2 o algo posterior falla, los tokens ya
    quedaron revocados: el usuario inicia sesión (su contraseña sigue sirviendo) y repite la
    petición. El borrado es idempotente.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        hasher: PasswordHasher,
        almacen: AlmacenDocumentos,
        revocacion: RevocacionTokens,
        reloj: Callable[[], datetime],
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._almacen = almacen
        self._revocacion = RevocacionDoble(revocacion, reloj)
        self._reloj = reloj

    async def execute(self, cmd: SuprimirDatosCommand) -> None:
        await self._comprobar_password(cmd)
        # Hash real de un secreto descartado: nadie conoce la contraseña y verify sigue
        # funcionando sobre esta fila.
        password_hash = await asyncio.to_thread(self._hasher.hash, secrets.token_urlsafe(32))

        async with self._uow as uow:
            admins_activos = await uow.usuarios.bloquear_admins_activos()
            usuario = await uow.usuarios.find_by_id_para_actualizar(cmd.usuario_id)
            if usuario is None or usuario.suprimido:
                # Otra petición igual terminó mientras esta esperaba el bloqueo.
                return
            if usuario.rol is Rol.ADMIN and usuario.activo and admins_activos <= 1:
                raise UltimoAdminError()

            ahora = self._reloj()
            await self._revocacion.antes_del_commit(cmd.usuario_id, ahora)
            objetos = await self._almacen.borrar_prefijo(f"{cmd.usuario_id}/")

            await uow.usuarios.suprimir_datos(cmd.usuario_id, password_hash, ahora)
            await uow.documentos.borrar_motivos_rechazo(cmd.usuario_id)
            await uow.auditoria.registrar(
                accion="DATA_SUPPRESSION",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=cmd.usuario_id,
                ip_origen=cmd.ip_origen,
                detalles={"rol": usuario.rol.value, "objetos_borrados": objetos},
            )
            if usuario.rol is Rol.PRESTADOR and usuario.activo:
                # suspendido_por es el propio usuario: aquí no actúa ningún Admin (C-48).
                await uow.outbox.agregar(
                    PrestadorSuspendido(
                        ocurrido_en=ahora,
                        usuario_id=cmd.usuario_id,
                        suspendido_por=cmd.usuario_id,
                    )
                )
            await uow.commit()
        await self._revocacion.despues_del_commit(cmd.usuario_id)

    async def _comprobar_password(self, cmd: SuprimirDatosCommand) -> None:
        async with self._uow as uow:
            usuario: Usuario | None = await uow.usuarios.find_by_id(cmd.usuario_id)
        if usuario is not None and await asyncio.to_thread(
            self._hasher.verify, cmd.password, usuario.password_hash
        ):
            return
        # Se confirma aunque la acción se rechace: el intento queda en la bitácora.
        async with self._uow as uow:
            await uow.auditoria.registrar(
                accion="DATA_SUPPRESSION",
                resultado=ResultadoAuditoria.DENEGADO,
                usuario_id=cmd.usuario_id,
                ip_origen=cmd.ip_origen,
                detalles={"motivo": "password_incorrecta"},
            )
            await uow.commit()
        raise CredencialesInvalidasError("La contraseña no es correcta.")
