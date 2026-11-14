from dataclasses import dataclass
from enum import StrEnum

from app.domain.errors import DatoInvalido

MAX_BYTES_IMAGEN = 5 * 1024 * 1024


class TipoImagen(StrEnum):
    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"

    @property
    def extension(self) -> str:
        return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[self.value]


@dataclass(frozen=True, slots=True)
class ImagenSolicitada:
    """Imagen que el prestador va a subir: solo JPEG, PNG o WebP de hasta 5 MB.

    El tamaño se firma en la URL de subida, así el almacén rechaza un archivo distinto.
    """

    tipo: TipoImagen
    tamano_bytes: int

    def __post_init__(self) -> None:
        if not 1 <= self.tamano_bytes <= MAX_BYTES_IMAGEN:
            raise DatoInvalido(
                campo="tamano_bytes", regla="rango", minimo=1, maximo=MAX_BYTES_IMAGEN
            )
