from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.value_objects.catalogos import NivelAlerta


class AlertaEditar(BaseModel):
    """Lo que se puede cambiar de una alerta vigente; el destino no cambia."""

    model_config = ConfigDict(extra="forbid")

    nivel: NivelAlerta
    mensaje: TextoTraducidoDatos
    fecha_expiracion: AwareDatetime
