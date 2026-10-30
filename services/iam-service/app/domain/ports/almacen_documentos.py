from datetime import timedelta
from typing import Protocol

# C-30: el Admin abre cada documento con una URL que vale 5 minutos.
VALIDEZ_URL = timedelta(minutes=5)


class AlmacenDocumentos(Protocol):
    """Bucket privado de documentos de verificación (SeaweedFS con API S3)."""

    async def guardar(self, clave: str, contenido: bytes, tipo_contenido: str) -> None:
        """Lanza ServicioNoDisponibleError si el almacenamiento no responde."""
        ...

    def url_lectura(self, clave: str, tipo_contenido: str, nombre_archivo: str) -> str:
        """URL prefirmada de lectura que vale VALIDEZ_URL. Fija el tipo de contenido y el
        nombre con que el navegador muestra el archivo (no la llave interna)."""
        ...
