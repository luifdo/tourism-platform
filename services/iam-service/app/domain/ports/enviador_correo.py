from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Correo:
    # repr=False: destinatario y cuerpo (con el enlace) nunca deben llegar a un log.
    destinatario: str = field(repr=False)
    asunto: str
    texto: str = field(repr=False)
    html: str = field(repr=False)


class EnviadorCorreo(Protocol):
    async def enviar(self, correo: Correo) -> None:
        """Lanza ServicioNoDisponibleError si el servidor no acepta el correo."""
        ...
