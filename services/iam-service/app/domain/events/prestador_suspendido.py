import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from app.domain.events.evento_dominio import EventoDominio


@dataclass(frozen=True, kw_only=True)
class PrestadorSuspendido(EventoDominio):
    """`prestador.suspendido.v1` (C-17): catalog oculta el perfil y los servicios.

    `prestador_id` es el `usuario_id` del prestador (C-08). El contrato admite `motivo`,
    pero no se envía: es texto libre y el bus solo lleva identificadores (C-41).
    """

    tipo: ClassVar[str] = "prestador.suspendido"
    usuario_id: uuid.UUID
    suspendido_por: uuid.UUID

    def payload(self) -> dict[str, Any]:
        return {
            "prestador_id": str(self.usuario_id),
            "usuario_id": str(self.usuario_id),
            "suspendido_por": str(self.suspendido_por),
        }
