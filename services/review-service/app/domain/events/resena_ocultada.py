from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.evento_dominio import EventoDominio


@dataclass(frozen=True, kw_only=True)
class ResenaOcultada(EventoDominio):
    """`resena.ocultada.v1`: el Administrador la ocultó (UC29); catalog la quita del promedio.

    Trae la puntuación para que catalog la registre aunque llegue antes que su publicación.
    """

    tipo: ClassVar[str] = "resena.ocultada"
    resena_id: UUID
    servicio_id: UUID
    turista_id: UUID
    puntuacion: int
    moderada_por: UUID
    motivo: str

    def payload(self) -> dict[str, Any]:
        return {
            "resena_id": str(self.resena_id),
            "servicio_id": str(self.servicio_id),
            "turista_id": str(self.turista_id),
            "puntuacion": self.puntuacion,
            "moderada_por": str(self.moderada_por),
            "motivo": self.motivo,
        }
