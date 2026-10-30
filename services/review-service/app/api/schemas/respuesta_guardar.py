from pydantic import BaseModel, ConfigDict, Field


class RespuestaGuardar(BaseModel):
    """Cuerpo de `PUT /resenas/{id}/respuesta` (contrato `RespuestaGuardar`).

    Como el comentario, se guarda tal cual y se muestra como texto, nunca como HTML.
    """

    model_config = ConfigDict(extra="forbid")

    texto: str = Field(min_length=1, max_length=1000)
