import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.value_objects.enums import Idioma, Rol


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
    id: uuid.UUID | None = None
    creado_en: datetime | None = None
    actualizado_en: datetime | None = None
