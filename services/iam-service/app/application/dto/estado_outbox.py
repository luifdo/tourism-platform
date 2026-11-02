from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EstadoOutbox:
    """Para las métricas: cuántos eventos esperan y desde cuándo espera el más viejo.

    `pendientes` y `mas_antiguo` no cuentan los retenidos (C-63): una supresión retenida no
    debe parecer un relay atascado. Esos van aparte, por tipo, en `retenidos`.
    """

    pendientes: int
    mas_antiguo: datetime | None
    retenidos: Mapping[str, int] = field(default_factory=dict)
