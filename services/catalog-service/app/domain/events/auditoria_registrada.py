from dataclasses import dataclass, field
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.evento_dominio import EventoDominio
from app.domain.value_objects.catalogos import ResultadoAuditoria


@dataclass(frozen=True, kw_only=True)
class AuditoriaRegistrada(EventoDominio):
    """`auditoria.registrada.v1`: iam-service lo guarda en la bitácora inmutable (UC33, RNF-10).

    `accion` es un código estable en mayúsculas (`ZONA_CREADA`, `ACCESS_DENIED`...) y
    `detalles` lleva los identificadores necesarios para reconstruir qué pasó.
    """

    tipo: ClassVar[str] = "auditoria.registrada"
    usuario_id: UUID | None
    accion: str
    resultado: ResultadoAuditoria = ResultadoAuditoria.EXITO
    detalles: dict[str, Any] = field(default_factory=dict)
    ip_origen: str | None = None

    def payload(self) -> dict[str, Any]:
        datos = {
            "usuario_id": str(self.usuario_id) if self.usuario_id else None,
            "accion": self.accion,
            "resultado": self.resultado.value,
            "detalles": self.detalles,
        }
        return datos | ({"ip_origen": self.ip_origen} if self.ip_origen else {})
