"""Envío de correos por SMTP (implementa EnviadorCorreo), adaptado de catalog.

En producción con STARTTLS y credenciales en un Secret de Kubernetes; en desarrollo, Mailpit
(`docker-compose.dev.yml`) los recibe sin enviarlos.
"""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.domain.exceptions import ServicioNoDisponibleError
from app.domain.ports.enviador_correo import Correo

logger = logging.getLogger(__name__)


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
        try:
            await aiosmtplib.send(
                mensaje,
                hostname=self._host,
                port=self._puerto,
                username=self._usuario,
                password=self._clave,
                start_tls=self._starttls,
                timeout=self._timeout,
            )
        except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
            # Solo el tipo: el mensaje de error del servidor suele repetir el destinatario.
            logger.error("El servidor SMTP no aceptó el correo: %s", type(exc).__name__)
            raise ServicioNoDisponibleError() from exc
