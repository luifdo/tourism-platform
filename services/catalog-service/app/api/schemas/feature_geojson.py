from typing import Literal

from pydantic import BaseModel


class FeatureGeoJSON[G, P](BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: G
    properties: P
