from typing import Literal

from pydantic import BaseModel


class ColeccionGeoJSON[F](BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[F]
