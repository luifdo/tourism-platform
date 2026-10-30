from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.api.i18n.etiquetas import etiqueta
from app.application.dto.alerta_vista import AlertaVista
from app.domain.value_objects.catalogos import NivelAlerta
from app.domain.value_objects.idioma import Idioma


class PropiedadesAlertaMapa(BaseModel):
    id: UUID
    nivel: NivelAlerta
    nivel_etiqueta: str
    mensaje: str
    servicio_id: UUID | None
    zona: str | None  # código de la zona, si la alerta es de zona
    fecha_expiracion: datetime

    @classmethod
    def desde(cls, alerta: AlertaVista, idioma: Idioma) -> "PropiedadesAlertaMapa":
        return cls(
            id=alerta.id,
            nivel=alerta.nivel,
            nivel_etiqueta=etiqueta(alerta.nivel, idioma),
            mensaje=alerta.mensaje.en_idioma(idioma)[0],
            servicio_id=alerta.servicio_id,
            zona=alerta.zona.codigo if alerta.zona else None,
            fecha_expiracion=alerta.fecha_expiracion,
        )
