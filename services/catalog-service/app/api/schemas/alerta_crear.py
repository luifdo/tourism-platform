from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.value_objects.catalogos import NivelAlerta


class AlertaCrear(BaseModel):
    """Cuerpo de UC26. Exactamente uno de `servicio_id` o `zona` (código); lo valida el caso
    de uso. La fecha lleva zona horaria (`2026-11-05T18:00:00-05:00`)."""

    model_config = ConfigDict(extra="forbid")

    nivel: NivelAlerta
    mensaje: TextoTraducidoDatos
    fecha_expiracion: AwareDatetime
    servicio_id: UUID | None = None
    zona: str | None = None
