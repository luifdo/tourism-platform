from app.api.schemas.coleccion_geojson import ColeccionGeoJSON
from app.api.schemas.feature_geojson import FeatureGeoJSON
from app.api.schemas.geometria_poligonal import GeometriaPoligonal
from app.api.schemas.propiedades_zona_calor import PropiedadesZonaCalor
from app.application.dto.zona_con_saturacion import ZonaConSaturacion
from app.domain.value_objects.idioma import Idioma

FeatureZonaCalor = FeatureGeoJSON[GeometriaPoligonal, PropiedadesZonaCalor]


class ColeccionMapaCalor(ColeccionGeoJSON[FeatureZonaCalor]):
    @classmethod
    def desde(cls, zonas: list[ZonaConSaturacion], idioma: Idioma) -> "ColeccionMapaCalor":
        return cls(
            features=[
                FeatureZonaCalor(
                    geometry=GeometriaPoligonal(**z.zona.geometria),
                    properties=PropiedadesZonaCalor.desde(z, idioma),
                )
                for z in zonas
            ]
        )
