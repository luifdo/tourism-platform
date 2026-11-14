from dataclasses import dataclass
from uuid import UUID

from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class ServicioConBandera:
    """Servicio con índice ≥ 0,85: la Entidad puede emitir una alerta (UC26)."""

    servicio_id: UUID
    nombre: TextoTraducido
    indice: float
