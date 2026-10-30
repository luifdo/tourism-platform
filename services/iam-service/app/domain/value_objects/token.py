from dataclasses import dataclass, field
from datetime import datetime

from app.domain.value_objects.enums import Rol


@dataclass(frozen=True)
class TokenEmitido:
    access_token: str = field(repr=False)
    expires_in: int
    jti: str
    expira_en: datetime


@dataclass(frozen=True)
class ClaimsToken:
    sub: str
    rol: Rol
    jti: str
    iat: datetime
    exp: datetime
