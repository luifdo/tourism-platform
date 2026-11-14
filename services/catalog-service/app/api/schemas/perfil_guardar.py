from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos


class PerfilGuardar(BaseModel):
    """Los campos que no se envían quedan vacíos: el formulario manda el perfil completo."""

    model_config = ConfigDict(extra="forbid")

    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=200)
    politica_cancelacion: TextoTraducidoDatos | None = None
