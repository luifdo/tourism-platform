import enum
from dataclasses import dataclass

from app.domain.exceptions import ArchivoDemasiadoGrandeError, TipoArchivoNoPermitidoError

# C-30: PDF, JPG o PNG de hasta 5 MB.
TAMANO_MAXIMO = 5 * 1024 * 1024


class TipoArchivo(enum.Enum):
    """Tipos aceptados, reconocidos por su firma de bytes y no por la extensión ni por el
    Content-Type que declara el cliente (C-30)."""

    PDF = ("application/pdf", "pdf", b"%PDF-")
    JPEG = ("image/jpeg", "jpg", b"\xff\xd8\xff")
    PNG = ("image/png", "png", b"\x89PNG\r\n\x1a\n")

    def __init__(self, tipo_contenido: str, extension: str, firma: bytes) -> None:
        self.tipo_contenido = tipo_contenido
        self.extension = extension
        self.firma = firma

    @classmethod
    def de_tipo_contenido(cls, tipo_contenido: str) -> "TipoArchivo":
        return next(t for t in cls if t.tipo_contenido == tipo_contenido)


@dataclass(frozen=True)
class ArchivoDocumento:
    """Contenido de un documento de verificación ya validado."""

    contenido: bytes
    tipo: TipoArchivo

    @classmethod
    def validar(cls, contenido: bytes) -> "ArchivoDocumento":
        if len(contenido) > TAMANO_MAXIMO:
            raise ArchivoDemasiadoGrandeError()
        tipo = next((t for t in TipoArchivo if contenido.startswith(t.firma)), None)
        if tipo is None:
            raise TipoArchivoNoPermitidoError()
        return cls(contenido=contenido, tipo=tipo)

    @property
    def tamano_bytes(self) -> int:
        return len(self.contenido)
