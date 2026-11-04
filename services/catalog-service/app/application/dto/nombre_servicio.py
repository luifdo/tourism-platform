from dataclasses import dataclass
from uuid import UUID

from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class NombreServicio:
    """Nombre de un servicio, activo o no, para que la PWA lo muestre en reservas y reseñas.

    El nombre va en ambos idiomas; el adaptador HTTP elige el pedido por el usuario.
    """

    id: UUID
    nombre: TextoTraducido
    activo: bool
