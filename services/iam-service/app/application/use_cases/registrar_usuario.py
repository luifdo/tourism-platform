from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.entities.usuario import Usuario
from app.domain.exceptions import (
    HabeasDataNoAceptadoError,
    MenorDeEdadError,
    NombreInvalidoError,
    RolNoPermitidoError,
    UsuarioYaExisteError,
)
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.email import Email
from app.domain.value_objects.enums import Idioma, ResultadoAuditoria, Rol
from app.domain.value_objects.password import Password

ROLES_AUTORREGISTRO = frozenset({Rol.TURISTA, Rol.PRESTADOR})
NOMBRE_MIN = 2
NOMBRE_MAX = 150


@dataclass(frozen=True)
class RegistrarUsuarioCommand:
    email: str
    password: str = field(repr=False)
    nombre_completo: str
    rol: Rol
    habeas_data_aceptado: bool
    # Solo se valida; no se guarda en la base.
    es_mayor_de_edad: bool
    ip_origen: str | None
    idioma: Idioma = Idioma.ES


class RegistrarUsuario:
    """UC1 (registro) + UC6 (consentimiento de datos personales, Ley 1581)."""

    def __init__(
        self, uow: UnitOfWork, hasher: PasswordHasher, reloj: Callable[[], datetime]
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._reloj = reloj

    async def execute(self, cmd: RegistrarUsuarioCommand) -> Usuario:
        if not cmd.habeas_data_aceptado:
            raise HabeasDataNoAceptadoError()
        if not cmd.es_mayor_de_edad:
            raise MenorDeEdadError()
        if cmd.rol not in ROLES_AUTORREGISTRO:
            raise RolNoPermitidoError()
        email = Email(cmd.email)
        password = Password(cmd.password)
        nombre = cmd.nombre_completo.strip()
        if not NOMBRE_MIN <= len(nombre) <= NOMBRE_MAX:
            raise NombreInvalidoError()

        async with self._uow as uow:
            if await uow.usuarios.find_by_email(email) is not None:
                raise UsuarioYaExisteError()

        # Sin la conexión ocupada: la cola de Argon2 no debe agotar el pool (C-53). Si otro
        # registro con el mismo correo entra mientras tanto, add() responde con la UNIQUE.
        password_hash = await self._hasher.hash_limitado(password.value)

        async with self._uow as uow:
            ahora = self._reloj()
            usuario = await uow.usuarios.add(
                Usuario(
                    email=email.value,
                    password_hash=password_hash,
                    nombre_completo=nombre,
                    rol=cmd.rol,
                    activo=True,
                    email_verificado=False,
                    habeas_data_aceptado=True,
                    habeas_data_aceptado_en=ahora,
                    idioma=cmd.idioma,
                )
            )
            await uow.auditoria.registrar(
                accion="USER_REGISTER",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=usuario.id,
                ip_origen=cmd.ip_origen,
                detalles={"rol": cmd.rol.value},
            )
            await uow.commit()
        return usuario
