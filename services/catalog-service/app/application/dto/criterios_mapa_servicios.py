import math
from dataclasses import dataclass, field

from app.application.dto.escala_mapa import EscalaMapa
from app.application.dto.filtros_servicio import FiltrosServicio
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.geo import Bbox

MAXIMO_INDIVIDUALES = 1000


def _alinear(vista: Bbox, celda: float) -> Bbox:
    """Amplía la vista hasta el borde de las celdas de agrupación."""

    def abajo(valor: float, limite: float) -> float:
        return max(round(math.floor(valor / celda) * celda, 9), limite)

    def arriba(valor: float, limite: float) -> float:
        return min(round(math.ceil(valor / celda) * celda, 9), limite)

    return Bbox(
        min_lon=abajo(vista.min_lon, -180),
        min_lat=abajo(vista.min_lat, -90),
        max_lon=arriba(vista.max_lon, 180),
        max_lat=arriba(vista.max_lat, 90),
    )


@dataclass(frozen=True, slots=True)
class CriteriosMapaServicios:
    """Filtros de UC16 ya validados. Cuando se agrupa, es también la llave de la caché.

    Al agrupar, la vista se amplía al borde de las celdas: un grupo no cambia de conteo por
    mover el mapa unos píxeles (todos sus puntos entran o ninguno) y vistas casi iguales
    comparten la misma entrada de caché.
    """

    vista: Bbox
    escala: EscalaMapa
    categorias: tuple[Categoria, ...] = field(default_factory=tuple)
    zona: str | None = None
    filtros: FiltrosServicio = field(default_factory=FiltrosServicio)

    def __post_init__(self) -> None:
        object.__setattr__(self, "categorias", tuple(sorted(set(self.categorias))))
        if self.escala.agrupa:
            object.__setattr__(self, "vista", _alinear(self.vista, self.escala.celda_grados))
