from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.api.i18n.etiquetas import etiqueta
from app.api.schemas.zona_resumen_respuesta import ZonaResumenRespuesta
from app.application.dto.alerta_vista import AlertaVista
from app.domain.value_objects.catalogos import NivelAlerta
from app.domain.value_objects.idioma import Idioma


class AlertaRespuesta(BaseModel):
    id: UUID
    nivel: NivelAlerta
    nivel_etiqueta: str
    mensaje: str
    servicio_id: UUID | None
    zona: ZonaResumenRespuesta | None
    fecha_expiracion: datetime

    @classmethod
    def desde(cls, alerta: AlertaVista, idioma: Idioma) -> "AlertaRespuesta":
        return cls(
            id=alerta.id,
            nivel=alerta.nivel,
            nivel_etiqueta=etiqueta(alerta.nivel, idioma),
            mensaje=alerta.mensaje.en_idioma(idioma)[0],
            servicio_id=alerta.servicio_id,
            zona=ZonaResumenRespuesta.desde(alerta.zona, idioma),
            fecha_expiracion=alerta.fecha_expiracion,
        )
