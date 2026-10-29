from dataclasses import dataclass
from uuid import UUID

from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class ServicioEnMapa:
    """Marcador de un servicio: lo justo para el globo del mapa; la ficha se pide aparte."""

    id: UUID
    nombre: TextoTraducido
    categoria: Categoria
    ubicacion: Coordenada
    calificacion_promedio: float | None
