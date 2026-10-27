from app.api.schemas.coleccion_geojson import ColeccionGeoJSON
from app.api.schemas.feature_geojson import FeatureGeoJSON
from app.api.schemas.geometria_poligonal import GeometriaPoligonal
from app.api.schemas.propiedades_alerta_mapa import PropiedadesAlertaMapa
from app.api.schemas.punto_geojson import PuntoGeoJSON
from app.application.dto.alerta_en_mapa import AlertaEnMapa
from app.domain.value_objects.idioma import Idioma

FeatureAlerta = FeatureGeoJSON[PuntoGeoJSON | GeometriaPoligonal, PropiedadesAlertaMapa]


class ColeccionAlertasMapa(ColeccionGeoJSON[FeatureAlerta]):
    @classmethod
    def desde(cls, alertas: list[AlertaEnMapa], idioma: Idioma) -> "ColeccionAlertasMapa":
        return cls(
            features=[
                FeatureAlerta(
                    geometry=a.geometria,
                    properties=PropiedadesAlertaMapa.desde(a.alerta, idioma),
                )
                for a in alertas
            ]
        )
