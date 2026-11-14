from fastapi.responses import JSONResponse


class RespuestaGeoJSON(JSONResponse):
    """Tipo de contenido de GeoJSON (RFC 7946), para que Leaflet y QGIS lo lean como tal."""

    media_type = "application/geo+json"
