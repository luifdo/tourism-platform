from typing import Annotated

from pydantic import Field

from app.api.schemas.coleccion_geojson import ColeccionGeoJSON
from app.api.schemas.feature_geojson import FeatureGeoJSON
from app.api.schemas.propiedades_grupo_mapa import PropiedadesGrupoMapa
from app.api.schemas.propiedades_servicio_mapa import PropiedadesServicioMapa
from app.api.schemas.punto_geojson import PuntoGeoJSON
from app.application.dto.mapa_servicios import MapaServicios
from app.domain.value_objects.idioma import Idioma

PropiedadesPunto = Annotated[
    PropiedadesServicioMapa | PropiedadesGrupoMapa, Field(discriminator="tipo")
]


class ColeccionServiciosMapa(ColeccionGeoJSON[FeatureGeoJSON[PuntoGeoJSON, PropiedadesPunto]]):
    @classmethod
    def desde(cls, mapa: MapaServicios, idioma: Idioma) -> "ColeccionServiciosMapa":
        servicios = [
            FeatureGeoJSON[PuntoGeoJSON, PropiedadesPunto](
                geometry=PuntoGeoJSON.desde(s.ubicacion),
                properties=PropiedadesServicioMapa.desde(s, idioma),
            )
            for s in mapa.servicios
        ]
        grupos = [
            FeatureGeoJSON[PuntoGeoJSON, PropiedadesPunto](
                geometry=PuntoGeoJSON.desde(g.ubicacion),
                properties=PropiedadesGrupoMapa.desde(g),
            )
            for g in mapa.grupos
        ]
        return cls(features=servicios + grupos)
