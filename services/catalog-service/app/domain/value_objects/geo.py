"""Objetos de valor geográficos. Siempre en WGS 84 (SRID 4326).

En GeoJSON el orden es `[lon, lat]`; aquí los campos tienen nombre para no confundirlos.
"""

from dataclasses import dataclass
from typing import Any

from app.domain.errors import DatoInvalido


def _validar_lat_lon(lat: float, lon: float) -> None:
    if not -90 <= lat <= 90:
        raise DatoInvalido(campo="lat", regla="rango", minimo=-90, maximo=90)
    if not -180 <= lon <= 180:
        raise DatoInvalido(campo="lon", regla="rango", minimo=-180, maximo=180)


@dataclass(frozen=True, slots=True)
class Coordenada:
    lat: float
    lon: float

    def __post_init__(self) -> None:
        _validar_lat_lon(self.lat, self.lon)


@dataclass(frozen=True, slots=True)
class Bbox:
    """Vista del mapa: esquina suroeste y noreste."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def __post_init__(self) -> None:
        _validar_lat_lon(self.min_lat, self.min_lon)
        _validar_lat_lon(self.max_lat, self.max_lon)
        if self.min_lon >= self.max_lon or self.min_lat >= self.max_lat:
            raise DatoInvalido(campo="bbox", regla="minimo_menor_que_maximo")

    @classmethod
    def desde_lista(cls, valores: list[float]) -> "Bbox":
        if len(valores) != 4:
            raise DatoInvalido(campo="bbox", regla="cuatro_valores")
        return cls(*valores)


@dataclass(frozen=True, slots=True)
class PoligonoGeoJSON:
    """Geometría GeoJSON `Polygon` o `MultiPolygon` validada en su forma.

    Se normaliza siempre a `MultiPolygon` (como se guarda en PostGIS), para que la misma
    zona enviada de una u otra forma sea igual. La validez topológica (anillos que se
    cruzan) la comprueba PostGIS con `ST_IsValid`.
    """

    tipo: str
    coordenadas: tuple

    def __post_init__(self) -> None:
        if self.tipo == "Polygon":
            object.__setattr__(self, "tipo", "MultiPolygon")
            object.__setattr__(self, "coordenadas", (self.coordenadas,))
        elif self.tipo != "MultiPolygon":
            raise DatoInvalido(
                campo="poligono", regla="tipo", permitidos=["Polygon", "MultiPolygon"]
            )
        poligonos = list(self.coordenadas)
        if not poligonos:
            raise DatoInvalido(campo="poligono", regla="sin_poligonos")
        for anillos in poligonos:
            if not anillos:
                raise DatoInvalido(campo="poligono", regla="sin_anillos")
            for anillo in anillos:
                self._validar_anillo(anillo)

    @staticmethod
    def _validar_anillo(anillo: Any) -> None:
        if len(anillo) < 4:
            raise DatoInvalido(campo="poligono", regla="anillo_minimo_4_puntos")
        for punto in anillo:
            if len(punto) != 2:
                raise DatoInvalido(campo="poligono", regla="punto_lon_lat")
            _validar_lat_lon(lat=punto[1], lon=punto[0])
        if tuple(anillo[0]) != tuple(anillo[-1]):
            raise DatoInvalido(campo="poligono", regla="anillo_cerrado")

    @classmethod
    def desde_geojson(cls, geometria: dict[str, Any]) -> "PoligonoGeoJSON":
        try:
            return cls(tipo=geometria["type"], coordenadas=_a_tuplas(geometria["coordinates"]))
        except (KeyError, TypeError) as exc:
            raise DatoInvalido(campo="poligono", regla="geojson") from exc

    def a_geojson(self) -> dict[str, Any]:
        return {"type": self.tipo, "coordinates": _a_listas(self.coordenadas)}


def _a_tuplas(valor: Any) -> Any:
    return tuple(_a_tuplas(v) for v in valor) if isinstance(valor, list | tuple) else valor


def _a_listas(valor: Any) -> Any:
    return [_a_listas(v) for v in valor] if isinstance(valor, tuple) else valor
