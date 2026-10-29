from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.api.i18n.etiquetas import etiqueta
from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.application.dto.alerta_editable import AlertaEditable
from app.application.dto.estado_alerta import EstadoAlerta
from app.domain.value_objects.catalogos import NivelAlerta
from app.domain.value_objects.idioma import Idioma


class AlertaEditableRespuesta(BaseModel):
    """Alerta como la administra la Entidad: mensaje en ambos idiomas, estado y versión."""

    id: UUID
    nivel: NivelAlerta
    nivel_etiqueta: str
    mensaje: TextoTraducidoDatos
    servicio_id: UUID | None
    zona: str | None
    estado: EstadoAlerta
    estado_etiqueta: str
    activa: bool
    fecha_expiracion: datetime
    creada_en: datetime
    entidad_usuario_id: UUID
    version: int

    @classmethod
    def desde(
        cls, editable: AlertaEditable, idioma: Idioma, ahora: datetime
    ) -> "AlertaEditableRespuesta":
        a, estado = editable.alerta, editable.estado(ahora)
        return cls(
            id=a.id,
            nivel=a.nivel,
            nivel_etiqueta=etiqueta(a.nivel, idioma),
            mensaje=TextoTraducidoDatos.desde(a.mensaje),
            servicio_id=a.servicio_id,
            zona=editable.zona_codigo,
            estado=estado,
            estado_etiqueta=etiqueta(estado, idioma),
            activa=a.activa,
            fecha_expiracion=a.fecha_expiracion,
            creada_en=a.creada_en,
            entidad_usuario_id=a.entidad_usuario_id,
            version=a.version,
        )
