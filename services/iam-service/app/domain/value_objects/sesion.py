import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SesionCreada:
    refresh_token: str = field(repr=False)
    familia: str
    expira_en: datetime
    expires_in: int


@dataclass(frozen=True)
class RotacionOk:
    nuevo_token: str = field(repr=False)
    familia: str
    usuario_id: uuid.UUID
    expires_in: int


@dataclass(frozen=True)
class RotacionInvalida:
    """El token no existe o ya venció: en Valkey no se distinguen."""


@dataclass(frozen=True)
class RotacionRevocada:
    familia: str
    usuario_id: uuid.UUID


@dataclass(frozen=True)
class RotacionReutilizada:
    familia: str
    usuario_id: uuid.UUID


ResultadoRotacion = RotacionOk | RotacionInvalida | RotacionRevocada | RotacionReutilizada
