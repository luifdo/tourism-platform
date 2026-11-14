from uuid import UUID

from pydantic import BaseModel

from app.api.schemas.geometria_poligonal import GeometriaPoligonal
from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.entities.zona import Zona


class ZonaEditableRespuesta(BaseModel):
    """Zona como la edita la Entidad: textos en ambos idiomas y el polígono completo."""

    id: UUID
    codigo: str
    nombre: TextoTraducidoDatos
    poligono: GeometriaPoligonal
    activa: bool
    version: int

    @classmethod
    def desde(cls, zona: Zona) -> "ZonaEditableRespuesta":
        geojson = zona.poligono.a_geojson()
        return cls(
            id=zona.id,
            codigo=zona.codigo.valor,
            nombre=TextoTraducidoDatos.desde(zona.nombre),
            poligono=GeometriaPoligonal(type=geojson["type"], coordinates=geojson["coordinates"]),
            activa=zona.activa,
            version=zona.version,
        )
