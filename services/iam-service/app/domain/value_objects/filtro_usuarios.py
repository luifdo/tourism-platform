from dataclasses import dataclass

from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import Rol


@dataclass(frozen=True)
class FiltroUsuarios:
    """Búsqueda de UC27. `q` busca en el nombre y en el correo (sin distinguir mayúsculas)."""

    rol: Rol | None = None
    activo: bool | None = None
    q: str | None = None
    pagina: int = 1
    tamano: int = 20


@dataclass(frozen=True)
class PaginaUsuarios:
    items: list[Usuario]
    total: int
    pagina: int
    tamano: int
