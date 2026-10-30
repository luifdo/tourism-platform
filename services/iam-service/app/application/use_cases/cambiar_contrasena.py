import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.application.use_cases.revocacion_doble import RevocacionDoble
from app.domain.exceptions import PasswordActualIncorrectaError, UsuarioNoEncontradoError
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.revocacion_tokens import RevocacionTokens
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import ResultadoAuditoria
from app.domain.value_objects.password import Password


@dataclass(frozen=True)
class CambiarContrasenaCommand:
    usuario_id: uuid.UUID
    password_actual: str = field(repr=False)
    password_nueva: str = field(repr=False)
    ip_origen: str | None


class CambiarContrasena:
    """UC4: cambio de contraseña con la sesión iniciada (C-52).

    Contraseña actual incorrecta: 422, con su fila `PASSWORD_CHANGE` / `Denegado` en una
    transacción propia. Si es correcta: política, hash y `PASSWORD_CHANGE` / `Exito`, con la
    doble revocación por usuario (C-21). No se emite un token nuevo: la regla `iat <= marca`
    también revocaría uno emitido en este mismo segundo, así que la PWA inicia sesión otra vez.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        hasher: PasswordHasher,
        revocacion: RevocacionTokens,
        reloj: Callable[[], datetime],
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._revocacion = RevocacionDoble(revocacion, reloj)
        self._reloj = reloj

    async def execute(self, cmd: CambiarContrasenaCommand) -> None:
        async with self._uow as uow:
            usuario = await uow.usuarios.find_by_id(cmd.usuario_id)
        if usuario is None or usuario.suprimido:
            raise UsuarioNoEncontradoError()

        # Argon2 es costoso en CPU: fuera del event loop y sin la fila bloqueada.
        if not await asyncio.to_thread(
            self._hasher.verify, cmd.password_actual, usuario.password_hash
        ):
            await self._registrar_rechazo(cmd)
            raise PasswordActualIncorrectaError()
        nueva = Password(cmd.password_nueva)
        password_hash = await asyncio.to_thread(self._hasher.hash, nueva.value)

        async with self._uow as uow:
            bloqueado = await uow.usuarios.find_by_id_para_actualizar(cmd.usuario_id)
            if bloqueado is None or bloqueado.suprimido:
                raise UsuarioNoEncontradoError()
            await uow.usuarios.actualizar_password_hash(cmd.usuario_id, password_hash)
            await uow.auditoria.registrar(
                accion="PASSWORD_CHANGE",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=cmd.usuario_id,
                ip_origen=cmd.ip_origen,
                detalles={},
            )
            await self._revocacion.antes_del_commit(cmd.usuario_id, self._reloj())
            await uow.commit()
        await self._revocacion.despues_del_commit(cmd.usuario_id)

    async def _registrar_rechazo(self, cmd: CambiarContrasenaCommand) -> None:
        async with self._uow as uow:
            await uow.auditoria.registrar(
                accion="PASSWORD_CHANGE",
                resultado=ResultadoAuditoria.DENEGADO,
                usuario_id=cmd.usuario_id,
                ip_origen=cmd.ip_origen,
                detalles={"motivo": "password_actual_incorrecta"},
            )
            await uow.commit()
