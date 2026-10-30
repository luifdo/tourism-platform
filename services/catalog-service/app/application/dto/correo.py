from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Correo:
    """Correo listo para enviar, con versión HTML y de texto plano."""

    destinatario: str
    asunto: str
    html: str
    texto: str
