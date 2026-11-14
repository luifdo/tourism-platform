import logging
import secrets
import uuid
from dataclasses import dataclass
from typing import Literal

from app.application.correo_recuperacion import correo_recuperacion
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import EmailInvalidoError, ServicioNoDisponibleError
from app.domain.ports.enviador_correo import EnviadorCorreo
from app.domain.ports.tokens_recuperacion import TokensRecuperacion
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.email import Email
from app.domain.value_objects.enums import ResultadoAuditoria

logger = logging.getLogger(__name__)

ResultadoRecuperacion = Literal[
    "enviado", "no_elegible", "enfriamiento", "fallo_valkey", "fallo_smtp", "fallo_base"
]


@dataclass(frozen=True)
class SolicitarRecuperacionCommand:
    email: str
    ip_origen: str | None


class SolicitarRecuperacion:
    """UC3, primer paso (C-28). Corre en segundo plano, después de responder 202 (C-50).

    Nunca lanza una excepción ni registra el correo intentado: el resultado solo sirve para la
    métrica. Pasos, si la cuenta existe, está activa y conserva sus datos:

    1. Reserva la espera de 60 s por usuario; dentro de ella no hace nada más.
    2. Guarda el SHA-256 de un token nuevo, que invalida el anterior.
    3. Audita `PASSWORD_RESET_REQUEST`: no sale ningún correo sin su fila.
    4. Envía el correo. Si no se pudo, descarta el token y la espera para que el usuario lo
       pida de nuevo de inmediato.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        tokens: TokensRecuperacion,
        enviador: EnviadorCorreo,
        pwa_url: str,
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._enviador = enviador
        self._pwa_url = pwa_url.rstrip("/")

    async def execute(self, cmd: SolicitarRecuperacionCommand) -> ResultadoRecuperacion:
        try:
            return await self._procesar(cmd)
        except ServicioNoDisponibleError:
            logger.error("Recuperación sin procesar: Valkey no responde")
            return "fallo_valkey"
        except Exception as exc:
            logger.error("Recuperación sin procesar: %s", type(exc).__name__)
            return "fallo_base"

    async def _procesar(self, cmd: SolicitarRecuperacionCommand) -> ResultadoRecuperacion:
        usuario = await self._elegible(cmd.email)
        if usuario is None or usuario.id is None:
            return "no_elegible"
        if not await self._tokens.reservar_envio(usuario.id):
            return "enfriamiento"

        token = secrets.token_urlsafe(32)
        try:
            await self._tokens.guardar(token, usuario.id)
            await self._auditar(usuario.id, cmd.ip_origen)
        except Exception:
            await self._descartar(usuario.id)
            raise
        try:
            await self._enviador.enviar(
                correo_recuperacion(
                    usuario.email,
                    usuario.nombre_completo,
                    usuario.idioma,
                    f"{self._pwa_url}/restablecer-contrasena?token={token}",
                )
            )
        except ServicioNoDisponibleError:
            logger.error("No se envió el correo de recuperación del usuario %s", usuario.id)
            await self._descartar(usuario.id)
            return "fallo_smtp"
        except Exception:
            await self._descartar(usuario.id)
            raise
        return "enviado"

    async def _elegible(self, email_texto: str) -> Usuario | None:
        try:
            email = Email(email_texto)
        except EmailInvalidoError:
            return None
        async with self._uow as uow:
            usuario = await uow.usuarios.find_by_email(email)
        if usuario is None or not usuario.activo or usuario.suprimido:
            return None
        return usuario

    async def _auditar(self, usuario_id: uuid.UUID, ip_origen: str | None) -> None:
        async with self._uow as uow:
            await uow.auditoria.registrar(
                accion="PASSWORD_RESET_REQUEST",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=usuario_id,
                ip_origen=ip_origen,
                detalles={},
            )
            await uow.commit()

    async def _descartar(self, usuario_id: uuid.UUID) -> None:
        try:
            await self._tokens.descartar(usuario_id)
        except ServicioNoDisponibleError:
            # El token nunca llegó a nadie; la espera y el token expiran solos.
            logger.error("No se pudo descartar el token de recuperación sin enviar")
