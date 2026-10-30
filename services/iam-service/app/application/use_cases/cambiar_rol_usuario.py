from dataclasses import dataclass

from app.application.use_cases.cambio_administrativo import (
    CambioAdministrativo,
    CambioAdministrativoCommand,
)
from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import Rol


@dataclass(frozen=True)
class CambiarRolCommand(CambioAdministrativoCommand):
    rol: Rol


class CambiarRolUsuario(CambioAdministrativo):
    """UC27: el Admin cambia el rol de una cuenta (`ROLE_CHANGE`, C-19).

    Si un Prestador pasa a otro rol, publica `prestador.suspendido`. Hacia Prestador no se
    publica nada: la aprobación depende de sus documentos (bloque 5, C-42).
    """

    accion = "ROLE_CHANGE"

    async def execute(self, cmd: CambiarRolCommand) -> Usuario:
        return await self._aplicar(cmd, lambda u: (cmd.rol, u.activo))
