"""Correo de recuperación de contraseña (UC3, C-28), en el idioma del usuario."""

from html import escape

from app.domain.ports.enviador_correo import Correo
from app.domain.ports.tokens_recuperacion import VALIDEZ_TOKEN
from app.domain.value_objects.enums import Idioma

_MINUTOS = int(VALIDEZ_TOKEN.total_seconds() // 60)

_TEXTOS = {
    Idioma.ES: {
        "asunto": "Restablece tu contraseña",
        "saludo": "Hola, {nombre}:",
        "cuerpo": "Recibimos una solicitud para restablecer la contraseña de tu cuenta en la "
        "plataforma de turismo de Santa Marta.",
        "accion": "Restablecer contraseña",
        "duracion": f"El enlace vale {_MINUTOS} minutos y solo se puede usar una vez.",
        "aviso": "Si no lo pediste, ignora este correo: tu contraseña no cambiará.",
    },
    Idioma.EN: {
        "asunto": "Reset your password",
        "saludo": "Hello, {nombre}:",
        "cuerpo": "We received a request to reset the password of your account on the Santa "
        "Marta tourism platform.",
        "accion": "Reset password",
        "duracion": f"The link is valid for {_MINUTOS} minutes and can only be used once.",
        "aviso": "If you did not request it, ignore this email: your password will not change.",
    },
}


def correo_recuperacion(destinatario: str, nombre: str, idioma: Idioma, enlace: str) -> Correo:
    textos = _TEXTOS[idioma]
    saludo = textos["saludo"]
    texto = (
        f"{saludo.format(nombre=nombre)}\n\n{textos['cuerpo']}\n\n{enlace}\n\n"
        f"{textos['duracion']}\n{textos['aviso']}\n"
    )
    # El nombre lo escribe el usuario: se escapa para que no inyecte HTML en el correo.
    html = (
        f"<p>{saludo.format(nombre=escape(nombre))}</p>"
        f"<p>{textos['cuerpo']}</p>"
        f'<p><a href="{escape(enlace, quote=True)}">{textos["accion"]}</a></p>'
        f"<p>{textos['duracion']}</p>"
        f"<p>{textos['aviso']}</p>"
    )
    return Correo(destinatario=destinatario, asunto=textos["asunto"], texto=texto, html=html)
