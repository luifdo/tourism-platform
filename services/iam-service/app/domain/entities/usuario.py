import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.value_objects.enums import Idioma, Rol

# Valores neutros de una cuenta suprimida (C-27). El dominio `invalid` está reservado (RFC 2606)
# y nunca recibe correo; el id mantiene la unicidad de la columna.
NOMBRE_SUPRIMIDO = "Usuario suprimido"


def email_suprimido(usuario_id: uuid.UUID) -> str:
    return f"suprimido+{usuario_id}@invalid"


@dataclass(kw_only=True)
class Usuario:
    """Cuenta de usuario. id, creado_en y actualizado_en los asigna la persistencia."""

    email: str
    password_hash: str = field(repr=False)
    nombre_completo: str
    rol: Rol
    activo: bool = True
    email_verificado: bool = False
    habeas_data_aceptado: bool
    habeas_data_aceptado_en: datetime
    idioma: Idioma = Idioma.ES
    # Del RUT, para `prestador.aprobado` (C-07).
    razon_social: str | None = None
    # Sube con cada edición del perfil; es su ETag (C-49).
    version: int = 1
    # No nulo cuando los datos personales se suprimieron (C-27).
    datos_suprimidos_en: datetime | None = None
    id: uuid.UUID | None = None
    creado_en: datetime | None = None
    actualizado_en: datetime | None = None

    @property
    def suprimido(self) -> bool:
        return self.datos_suprimidos_en is not None
