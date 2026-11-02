import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from app.domain.events.evento_dominio import EventoDominio
from app.domain.value_objects.enums import Rol


@dataclass(frozen=True, kw_only=True)
class UsuarioSuprimido(EventoDominio):
    """`usuario.suprimido.v1` (Ley 1581, C-27): cada consumidor borra los datos personales que
    guarde de ese usuario. catalog borra `razon_social`, `telefono` y `direccion` del perfil.

    Se publica para todos los roles: quien no tiene datos de ese usuario lo ignora. Mientras
    catalog no esté desplegado con su cola, el relay lo retiene (C-63).
    """

    tipo: ClassVar[str] = "usuario.suprimido"
    usuario_id: uuid.UUID
    rol: Rol

    def payload(self) -> dict[str, Any]:
        return {"usuario_id": str(self.usuario_id), "rol": self.rol.value}
