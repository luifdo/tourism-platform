import uuid
from dataclasses import dataclass, field

from app.domain.entities.documento_verificacion import DocumentoVerificacion, EstadoVerificacion


@dataclass(frozen=True)
class FiltroPrestadores:
    """Cola de revisión de UC28: cuentas con rol Prestador, por estado de verificación."""

    estado: EstadoVerificacion | None = None
    pagina: int = 1
    tamano: int = 20


@dataclass(frozen=True)
class ResumenPrestador:
    usuario_id: uuid.UUID
    nombre_completo: str
    email: str
    activo: bool
    razon_social: str | None
    estado: EstadoVerificacion
    vigentes: list[DocumentoVerificacion] = field(default_factory=list)


@dataclass(frozen=True)
class PaginaPrestadores:
    items: list[ResumenPrestador]
    total: int
    pagina: int
    tamano: int
