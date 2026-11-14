from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


class RecomendacionSinJustificacionError(ValueError):
    """Toda recomendación debe explicar por qué se sugiere (RNF-08)."""


@dataclass(frozen=True)
class Recomendacion:
    """Servicio del catálogo que el chatbot le sugiere al turista, con su motivo."""

    servicio_id: UUID
    nombre: str
    justificacion: str

    def __post_init__(self) -> None:
        if not self.justificacion.strip():
            raise RecomendacionSinJustificacionError(self.servicio_id)


@dataclass(frozen=True)
class RegistroRecomendacion:
    """Fila de `recomendacion_log`. No lleva el texto de la conversación (Ley 1581)."""

    conversacion_id: UUID
    turista_id: UUID
    servicio_id: UUID
    justificacion: str
    herramientas_usadas: list[str]
    modelo: str
    fecha_generacion: datetime
    id: UUID = field(default_factory=uuid4)
