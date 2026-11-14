from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.dto.zona_resumen import ZonaResumen
from app.domain.value_objects.catalogos import NivelAlerta
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class AlertaVista:
    id: UUID
    nivel: NivelAlerta
    mensaje: TextoTraducido
    servicio_id: UUID | None
    zona: ZonaResumen | None
    fecha_expiracion: datetime
