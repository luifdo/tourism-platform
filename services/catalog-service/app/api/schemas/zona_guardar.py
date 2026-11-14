from pydantic import BaseModel, ConfigDict

from app.api.schemas.geometria_poligonal import GeometriaPoligonal
from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.geo import PoligonoGeoJSON
from app.domain.value_objects.texto_traducido import TextoTraducido


class ZonaGuardar(BaseModel):
    """Cuerpo para crear o editar una zona. El patrón del código y la forma del polígono los
    valida el dominio, para responder con la regla exacta que se incumplió."""

    model_config = ConfigDict(extra="forbid")

    codigo: str
    nombre: TextoTraducidoDatos
    poligono: GeometriaPoligonal

    def a_dominio(self) -> tuple[CodigoZona, TextoTraducido, PoligonoGeoJSON]:
        return (
            CodigoZona(self.codigo),
            self.nombre.a_dominio(),
            PoligonoGeoJSON.desde_geojson(self.poligono.model_dump()),
        )
