from datetime import date
from uuid import UUID

from pydantic import BaseModel

from app.application.dto.servicio_pendiente import ServicioPendiente


class ServicioPendienteRespuesta(BaseModel):
    servicio_id: UUID
    ultima_visita: date

    @classmethod
    def desde(cls, pendiente: ServicioPendiente) -> "ServicioPendienteRespuesta":
        return cls(servicio_id=pendiente.servicio_id, ultima_visita=pendiente.ultima_visita)
