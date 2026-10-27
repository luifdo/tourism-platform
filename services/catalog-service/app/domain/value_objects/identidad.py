from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.domain.errors import RolNoPermitido


class Rol(StrEnum):
    """Valores de `X-Usuario-Rol` que reenvía Traefik tras validar el JWT."""

    TURISTA = "Turista"
    PRESTADOR = "Prestador"
    ENTIDAD = "Entidad"
    ADMIN = "Admin"


# Administran zonas y alertas oficiales (la Entidad de gestión del destino y el Admin).
ROLES_ENTIDAD = (Rol.ENTIDAD, Rol.ADMIN)


@dataclass(frozen=True, slots=True)
class Identidad:
    """Usuario autenticado de la petición; nunca la decide el cliente ni el chatbot."""

    usuario_id: UUID
    rol: Rol

    def exigir_rol(self, *permitidos: Rol) -> None:
        if self.rol not in permitidos:
            raise RolNoPermitido(rol=self.rol.value, permitidos=[r.value for r in permitidos])
