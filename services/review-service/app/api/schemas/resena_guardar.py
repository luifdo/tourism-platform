from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.aspectos_datos import AspectosDatos, PuntuacionDatos
from app.domain.value_objects.contenido_resena import ContenidoResena


class ResenaGuardar(BaseModel):
    """Cuerpo de `PUT /resenas/{id}` (contrato `ResenaGuardar`).

    El comentario se guarda tal cual: se muestra como texto, nunca como HTML.
    """

    model_config = ConfigDict(extra="forbid")

    puntuacion: PuntuacionDatos
    aspectos: AspectosDatos = Field(default_factory=AspectosDatos)
    comentario: str | None = Field(default=None, max_length=2000)

    def a_dominio(self) -> ContenidoResena:
        return ContenidoResena(self.puntuacion, self.aspectos.a_dominio(), self.comentario)
