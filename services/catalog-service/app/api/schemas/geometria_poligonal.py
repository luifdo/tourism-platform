from typing import Any, Literal

from pydantic import BaseModel


class GeometriaPoligonal(BaseModel):
    """`Polygon` o `MultiPolygon` tal como lo entrega PostGIS (ST_AsGeoJSON), en `[lon, lat]`."""

    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]
