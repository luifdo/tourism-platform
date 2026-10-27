from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from app.application.dto.filtros_servicio import FiltrosServicio
from app.domain.errors import DatoInvalido
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.idioma import Idioma

RADIO_POR_DEFECTO_M = 5000
RADIO_MAXIMO_M = 50000


class OrdenBusqueda(StrEnum):
    RELEVANCIA = "relevancia"
    DISTANCIA = "distancia"
    PRECIO = "precio"
    CALIFICACION = "calificacion"


@dataclass(frozen=True, slots=True)
class CriteriosBusqueda:
    """Filtros de UC7/UC8 ya validados. Es también la llave de la caché de búsqueda."""

    idioma: Idioma
    pagina: int = 1
    tamano: int = 20
    texto: str | None = None
    categorias: tuple[Categoria, ...] = field(default_factory=tuple)
    zona: str | None = None
    precio_min: Decimal | None = None
    precio_max: Decimal | None = None
    cerca_de: Coordenada | None = None
    radio_m: int = RADIO_POR_DEFECTO_M
    orden: OrdenBusqueda = OrdenBusqueda.CALIFICACION
    filtros: FiltrosServicio = field(default_factory=FiltrosServicio)

    def __post_init__(self) -> None:
        texto = self.texto.strip() if self.texto else None
        object.__setattr__(self, "texto", texto or None)
        object.__setattr__(self, "categorias", tuple(sorted(set(self.categorias))))
        if self.pagina < 1:
            raise DatoInvalido(campo="pagina", regla="minimo", minimo=1)
        if not 1 <= self.tamano <= 100:
            raise DatoInvalido(campo="tamano", regla="rango", minimo=1, maximo=100)
        if not 100 <= self.radio_m <= RADIO_MAXIMO_M:
            raise DatoInvalido(campo="radio_m", regla="rango", minimo=100, maximo=RADIO_MAXIMO_M)
        if (
            self.precio_min is not None
            and self.precio_max is not None
            and self.precio_min > self.precio_max
        ):
            raise DatoInvalido(campo="precio_min", regla="mayor_que", otro="precio_max")
        if self.orden is OrdenBusqueda.DISTANCIA and self.cerca_de is None:
            raise DatoInvalido(campo="orden", regla="requiere", requiere="lat, lon")
        if self.orden is OrdenBusqueda.RELEVANCIA and self.texto is None:
            raise DatoInvalido(campo="orden", regla="requiere", requiere="texto")
