import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.application.use_cases.revocacion_doble import RevocacionDoble
from app.domain.exceptions import TokenRecuperacionInvalidoError
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.revocacion_tokens import RevocacionTokens
from app.domain.ports.tokens_recuperacion import TokensRecuperacion
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import ResultadoAuditoria
from app.domain.value_objects.password import Password


@dataclass(frozen=True)
class RestablecerContrasenaCommand:
    token: str = field(repr=False)
    password: str = field(repr=False)
    ip_origen: str | None


class RestablecerContrasena:
    """UC3, segundo paso (C-28).

    1. Valida la política antes de tocar el token: una contraseña débil no gasta el enlace.
    2. Consume el token (GETDEL). Inválido, vencido o ya usado: 400 TOKEN_INVALIDO. Lo mismo si
       la cuenta se desactivó o se suprimió después de pedirlo.
    3. Calcula el hash después de consumir: Argon2 es costoso y esta ruta es pública, así que
       un token falso no debe gastar CPU.
    4. Guarda el hash y `PASSWORD_RESET`, con la doble revocación por usuario (C-21).

    Si la base o Valkey fallan después del paso 2, el enlace ya se gastó y hay que pedir otro.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        tokens: TokensRecuperacion,
        hasher: PasswordHasher,
        revocacion: RevocacionTokens,
        reloj: Callable[[], datetime],
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._hasher = hasher
        self._revocacion = RevocacionDoble(revocacion, reloj)
        self._reloj = reloj

    async def execute(self, cmd: RestablecerContrasenaCommand) -> None:
        password = Password(cmd.password)
        usuario_id = await self._tokens.consumir(cmd.token)
        if usuario_id is None:
            raise TokenRecuperacionInvalidoError()
        password_hash = await asyncio.to_thread(self._hasher.hash, password.value)

        async with self._uow as uow:
            usuario = await uow.usuarios.find_by_id_para_actualizar(usuario_id)
            if usuario is None or not usuario.activo or usuario.suprimido:
                raise TokenRecuperacionInvalidoError()
            await uow.usuarios.actualizar_password_hash(usuario_id, password_hash)
            await uow.auditoria.registrar(
                accion="PASSWORD_RESET",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=usuario_id,
                ip_origen=cmd.ip_origen,
                detalles={},
            )
            await self._revocacion.antes_del_commit(usuario_id, self._reloj())
            await uow.commit()
        await self._revocacion.despues_del_commit(usuario_id)
