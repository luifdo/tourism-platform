from dataclasses import dataclass, field
from datetime import datetime

from app.domain.value_objects.enums import Rol


@dataclass(frozen=True)
class TokenEmitido:
    access_token: str = field(repr=False)
    expires_in: int
    jti: str
    expira_en: datetime
    emitido_en: datetime


@dataclass(frozen=True)
class ClaimsToken:
    sub: str
    rol: Rol
    jti: str
    iat: datetime
    exp: datetime
    # Id de la familia de refresh; None en los tokens emitidos antes de C-20.
    sid: str | None = None
