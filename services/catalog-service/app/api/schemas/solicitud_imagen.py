from pydantic import BaseModel, ConfigDict

from app.domain.value_objects.imagen_solicitada import ImagenSolicitada, TipoImagen


class SolicitudImagen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_type: TipoImagen
    tamano_bytes: int

    def a_dominio(self) -> ImagenSolicitada:
        return ImagenSolicitada(tipo=self.content_type, tamano_bytes=self.tamano_bytes)
