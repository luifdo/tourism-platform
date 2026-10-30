import uuid
from dataclasses import dataclass, field

from app.domain.entities.usuario import Usuario
from app.domain.exceptions import (
    CredencialesInvalidasError,
    CuentaInactivaError,
    EmailInvalidoError,
)
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.token_service import TokenService
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.email import Email
from app.domain.value_objects.enums import ResultadoAuditoria
from app.domain.value_objects.token import TokenEmitido

# Hash Argon2id de una contraseña aleatoria descartada, con los mismos parámetros que los
# hashes reales (t=3, m=65536, p=4). Si el correo no existe se verifica contra él, para que
# el tiempo de respuesta no revele si la cuenta existe.
HASH_RELLENO = (
    "$argon2id$v=19$m=65536,t=3,p=4$TSPom5YJVmBUdV1Qjroqug$"
    "sryxr0ufBo+tNty+qRBDSD05sJYmG0WkAotEo3OFxj0"
)


@dataclass(frozen=True)
class IniciarSesionCommand:
    email: str
    password: str = field(repr=False)
    ip_origen: str | None


class IniciarSesion:
    """UC2: inicio de sesión con correo y contraseña; emite un access token RS256."""

    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, tokens: TokenService) -> None:
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens

    async def execute(self, cmd: IniciarSesionCommand) -> tuple[TokenEmitido, Usuario]:
        try:
            email: Email | None = Email(cmd.email)
        except EmailInvalidoError:
            # Un formato inválido se trata igual que un correo inexistente (401, no 422).
            email = None

        # La conexión se devuelve antes de Argon2: las peticiones en la cola del semáforo no
        # deben agotar el pool, que verificar necesita para auditar sus rechazos (C-53).
        async with self._uow as uow:
            encontrado = await uow.usuarios.find_by_email(email) if email is not None else None

        if encontrado is None:
            await self._hasher.verify_limitado(cmd.password, HASH_RELLENO)
            await self._registrar_fallo(None, "usuario_no_existe", cmd.ip_origen)
            raise CredencialesInvalidasError()

        if not await self._hasher.verify_limitado(cmd.password, encontrado.password_hash):
            await self._registrar_fallo(encontrado.id, "password_incorrecta", cmd.ip_origen)
            raise CredencialesInvalidasError()

        nuevo_hash = None
        if encontrado.activo and self._hasher.needs_rehash(encontrado.password_hash):
            nuevo_hash = await self._hasher.hash_limitado(cmd.password)

        assert encontrado.id is not None
        async with self._uow as uow:
            # Se lee otra vez porque la cola puede durar segundos: el token debe llevar el rol y
            # el estado de ahora, y no salir después de la segunda revocación de un cambio
            # que ya no vio (C-21, C-53).
            usuario = await uow.usuarios.find_by_id(encontrado.id)
            if usuario is None or usuario.password_hash != encontrado.password_hash:
                # La contraseña verificada ya no es la vigente.
                await self._fallo(uow, encontrado.id, "password_incorrecta", cmd.ip_origen)
                raise CredencialesInvalidasError()

            if not usuario.activo:
                await self._fallo(uow, usuario.id, "cuenta_inactiva", cmd.ip_origen)
                raise CuentaInactivaError()

            if nuevo_hash is not None:
                await uow.usuarios.actualizar_password_hash(encontrado.id, nuevo_hash)

            token = self._tokens.emitir(usuario)
            await uow.auditoria.registrar(
                accion="LOGIN_SUCCESS",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=usuario.id,
                ip_origen=cmd.ip_origen,
                detalles={},
            )
            await uow.commit()
        return token, usuario

    async def _registrar_fallo(
        self, usuario_id: uuid.UUID | None, motivo: str, ip_origen: str | None
    ) -> None:
        async with self._uow as uow:
            await self._fallo(uow, usuario_id, motivo, ip_origen)

    @staticmethod
    async def _fallo(
        uow: UnitOfWork, usuario_id: uuid.UUID | None, motivo: str, ip_origen: str | None
    ) -> None:
        # Se confirma aunque el login falle: el intento queda en la bitácora (RNF-10).
        # Nunca se guarda el correo intentado ni la contraseña.
        await uow.auditoria.registrar(
            accion="LOGIN_FAIL",
            resultado=ResultadoAuditoria.DENEGADO,
            usuario_id=usuario_id,
            ip_origen=ip_origen,
            detalles={"motivo": motivo},
        )
        await uow.commit()
