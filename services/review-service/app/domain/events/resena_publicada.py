from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.evento_dominio import EventoDominio


@dataclass(frozen=True, kw_only=True)
class ResenaPublicada(EventoDominio):
    """`resena.publicada.v1`: la reseña cuenta en el promedio con esta puntuación.

    Se emite al crearla, al editarla y al volver a publicarla desde `OCULTA`. catalog guarda
    una fila por `resena_id` e ignora lo que tenga `occurred_at` más viejo que lo aplicado.
    """

    tipo: ClassVar[str] = "resena.publicada"
    resena_id: UUID
    servicio_id: UUID
    turista_id: UUID
    puntuacion: int

    def payload(self) -> dict[str, Any]:
        return {
            "resena_id": str(self.resena_id),
            "servicio_id": str(self.servicio_id),
            "turista_id": str(self.turista_id),
            "puntuacion": self.puntuacion,
        }
