import uuid
from datetime import datetime
from typing import Protocol

from app.domain.entities.usuario import Usuario
from app.domain.value_objects.email import Email
from app.domain.value_objects.enums import Idioma, Rol
from app.domain.value_objects.filtro_usuarios import FiltroUsuarios, PaginaUsuarios


class UsuarioRepository(Protocol):
    async def add(self, usuario: Usuario) -> Usuario:
        """Persiste el usuario y lo devuelve con id y timestamps.

        Lanza UsuarioYaExisteError si el email ya está registrado.
        """
        ...

    async def find_by_email(self, email: Email) -> Usuario | None: ...

    async def find_by_id(self, usuario_id: uuid.UUID) -> Usuario | None: ...

    async def actualizar_password_hash(self, usuario_id: uuid.UUID, password_hash: str) -> None: ...

    async def listar(self, filtro: FiltroUsuarios) -> PaginaUsuarios: ...

    async def bloquear_admins_activos(self) -> int:
        """Bloquea (`FOR UPDATE`, en orden de id) los Admins activos y devuelve cuántos son.

        Todo cambio administrativo lo llama primero: así dos Admins no pueden quitarse el rol
        a la vez y dejar la plataforma sin ninguno (C-29), y el orden fijo evita interbloqueos.
        """
        ...

    async def find_by_id_para_actualizar(self, usuario_id: uuid.UUID) -> Usuario | None:
        """Como find_by_id, pero bloquea la fila hasta el fin de la transacción."""
        ...

    async def actualizar_razon_social(self, usuario_id: uuid.UUID, razon_social: str) -> None: ...

    async def actualizar_rol_y_estado(
        self, usuario_id: uuid.UUID, rol: Rol, activo: bool
    ) -> Usuario: ...

    async def actualizar_perfil(
        self, usuario_id: uuid.UUID, nombre_completo: str, idioma: Idioma
    ) -> Usuario:
        """Guarda los datos editables y sube la version (C-49)."""
        ...

    async def suprimir_datos(
        self, usuario_id: uuid.UUID, password_hash: str, suprimido_en: datetime
    ) -> None:
        """Reemplaza los datos personales por valores neutros y desactiva la cuenta (C-27)."""
        ...
