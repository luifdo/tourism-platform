import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from app.domain.events.evento_dominio import EventoDominio


@dataclass(frozen=True, kw_only=True)
class PrestadorAprobado(EventoDominio):
    """`prestador.aprobado.v1` (UC28): catalog crea el perfil o reactiva el suspendido.

    `prestador_id` es el `usuario_id` (C-08). `razon_social` viene del RUT (C-07); el
    contrato la admite opcional, así que se omite si no se conoce.
    """

    tipo: ClassVar[str] = "prestador.aprobado"
    usuario_id: uuid.UUID
    aprobado_por: uuid.UUID
    razon_social: str | None = None

    def payload(self) -> dict[str, Any]:
        payload = {
            "prestador_id": str(self.usuario_id),
            "usuario_id": str(self.usuario_id),
            "aprobado_por": str(self.aprobado_por),
        }
        if self.razon_social:
            payload["razon_social"] = self.razon_social
        return payload
