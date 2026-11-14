"""Envío de correos por SMTP (implementa EnviadorCorreo).

En producción con TLS (STARTTLS) y credenciales en un Secret de Kubernetes; en desarrollo,
Mailpit (`docker-compose.dev.yml`) los recibe sin enviarlos. Si el servidor no los acepta,
lanza la excepción y el consumidor reintenta.
"""

from email.message import EmailMessage

import aiosmtplib

from app.application.dto.correo import Correo


class EnviadorSmtp:
    def __init__(
        self,
        host: str,
        puerto: int,
        remitente: str,
        usuario: str | None,
        clave: str | None,
        starttls: bool,
        timeout_segundos: float,
    ) -> None:
        self._host = host
        self._puerto = puerto
        self._remitente = remitente
        self._usuario = usuario or None
        self._clave = clave or None
        self._starttls = starttls
        self._timeout = timeout_segundos

    async def enviar(self, correo: Correo) -> None:
        mensaje = EmailMessage()
        mensaje["From"] = self._remitente
        mensaje["To"] = correo.destinatario
        mensaje["Subject"] = correo.asunto
        mensaje.set_content(correo.texto)
        mensaje.add_alternative(correo.html, subtype="html")
        await aiosmtplib.send(
            mensaje,
            hostname=self._host,
            port=self._puerto,
            username=self._usuario,
            password=self._clave,
            start_tls=self._starttls,
            timeout=self._timeout,
        )
