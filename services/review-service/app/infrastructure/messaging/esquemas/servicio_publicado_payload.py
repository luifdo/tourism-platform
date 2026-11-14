from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ServicioPublicadoPayload(BaseModel):
    """Lo que review usa de `contracts/events/servicio.publicado.v1.json`: el dueño.

    `activo` se ignora a propósito: un servicio desactivado conserva sus reseñas y su dueño
    puede seguir respondiéndolas; un prestador suspendido ya no inicia sesión (iam).
    """

    model_config = ConfigDict(extra="ignore")

    servicio_id: UUID
    prestador_usuario_id: UUID
    version: int = Field(ge=1)
