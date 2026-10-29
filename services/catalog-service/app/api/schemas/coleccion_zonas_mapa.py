from app.api.schemas.coleccion_geojson import ColeccionGeoJSON
from app.api.schemas.feature_geojson import FeatureGeoJSON
from app.api.schemas.geometria_poligonal import GeometriaPoligonal
from app.api.schemas.propiedades_zona_mapa import PropiedadesZonaMapa
from app.application.dto.zona_en_mapa import ZonaEnMapa
from app.domain.value_objects.idioma import Idioma

FeatureZona = FeatureGeoJSON[GeometriaPoligonal, PropiedadesZonaMapa]


class ColeccionZonasMapa(ColeccionGeoJSON[FeatureZona]):
    @classmethod
    def desde(cls, zonas: list[ZonaEnMapa], idioma: Idioma) -> "ColeccionZonasMapa":
        return cls(
            features=[
                FeatureZona(
                    geometry=GeometriaPoligonal(**z.geometria),
                    properties=PropiedadesZonaMapa.desde(z, idioma),
                )
                for z in zonas
            ]
        )
