from dataclasses import dataclass

from app.application.use_cases.cambio_administrativo import (
    CambioAdministrativo,
    CambioAdministrativoCommand,
)
from app.domain.entities.usuario import Usuario


@dataclass(frozen=True)
class CambiarEstadoCommand(CambioAdministrativoCommand):
    activo: bool


class CambiarEstadoUsuario(CambioAdministrativo):
    """UC27: el Admin activa o desactiva una cuenta (`USER_STATUS_CHANGE`, C-19).

    Desactivar revoca los tokens del usuario y, si es un Prestador, publica
    `prestador.suspendido`. Reactivar a un Prestador con sus documentos aprobados publica
    `prestador.aprobado` (C-42).
    """

    accion = "USER_STATUS_CHANGE"

    async def execute(self, cmd: CambiarEstadoCommand) -> Usuario:
        return await self._aplicar(cmd, lambda u: (u.rol, cmd.activo))
