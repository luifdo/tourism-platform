from uuid import UUID

from pydantic import BaseModel

from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.entities.prestador_perfil import PrestadorPerfil


class PerfilEditableRespuesta(BaseModel):
    id: UUID
    razon_social: str | None
    telefono: str | None
    direccion: str | None
    politica_cancelacion: TextoTraducidoDatos | None
    activo: bool
    version: int

    @classmethod
    def desde(cls, perfil: PrestadorPerfil) -> "PerfilEditableRespuesta":
        politica = perfil.politica_cancelacion
        return cls(
            id=perfil.id,
            razon_social=perfil.razon_social,
            telefono=perfil.telefono,
            direccion=perfil.direccion,
            politica_cancelacion=TextoTraducidoDatos.desde(politica) if politica else None,
            activo=perfil.activo,
            version=perfil.version,
        )
