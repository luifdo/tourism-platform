from typing import Protocol
from uuid import UUID

from app.application.dto.subida_imagen import SubidaImagen
from app.domain.value_objects.imagen_solicitada import ImagenSolicitada


class AlmacenImagenes(Protocol):
    def url_subida(self, prestador_id: UUID, imagen: ImagenSolicitada) -> SubidaImagen:
        """URL firmada de un PUT con el tipo y el tamaño exactos de la imagen."""
        ...

    def origen_de(self, prestador_id: UUID) -> str:
        """Prefijo de las URL públicas de ese prestador: solo esas se aceptan en sus servicios."""
        ...
