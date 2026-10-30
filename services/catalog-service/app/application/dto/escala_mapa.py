"""Escala del mapa según el zoom de Leaflet sobre teselas de OpenStreetMap (256 px).

A zoom z el mundo mide 256·2^z píxeles de ancho, así que un píxel equivale a
360 / (256·2^z) grados. De ahí salen el tamaño de la celda que agrupa puntos y la tolerancia
con que se simplifican los polígonos: no se envía nada que no se vea en pantalla. En latitud
la equivalencia es aproximada (Mercator), pero cerca del ecuador, como en Santa Marta, la
diferencia es de un 2 %.
"""

from dataclasses import dataclass

from app.domain.errors import DatoInvalido

ZOOM_MINIMO = 0
ZOOM_MAXIMO = 19
ZOOM_INDIVIDUAL = 13  # desde este zoom se ven servicios sueltos
PIXELES_POR_GRUPO = 64


@dataclass(frozen=True, slots=True)
class EscalaMapa:
    zoom: int

    def __post_init__(self) -> None:
        if not ZOOM_MINIMO <= self.zoom <= ZOOM_MAXIMO:
            raise DatoInvalido(campo="zoom", regla="rango", minimo=ZOOM_MINIMO, maximo=ZOOM_MAXIMO)

    @property
    def grados_por_pixel(self) -> float:
        return 360 / (256 * 2**self.zoom)

    @property
    def agrupa(self) -> bool:
        return self.zoom < ZOOM_INDIVIDUAL

    @property
    def celda_grados(self) -> float:
        """Lado de la celda que agrupa puntos: unos 64 px en pantalla."""
        return self.grados_por_pixel * PIXELES_POR_GRUPO

    @property
    def tolerancia_grados(self) -> float:
        """Un píxel: lo que se simplifique por debajo no se nota."""
        return self.grados_por_pixel
