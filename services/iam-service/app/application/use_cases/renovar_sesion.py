import logging
from dataclasses import dataclass

from app.application.use_cases.registrar_acceso_denegado import RegistrarAccesoDenegado
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import ServicioNoDisponibleError, TokenInvalidoError
from app.domain.ports.sesiones_renovacion import SesionesRenovacion
from app.domain.ports.token_service import TokenService
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.sesion import (
    RotacionInvalida,
    RotacionOk,
    RotacionRevocada,
)
from app.domain.value_objects.token import TokenEmitido

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SesionRenovada:
    token: TokenEmitido
    usuario: Usuario
    rotacion: RotacionOk


class RenovarSesion:
    """Plan §2.3 y Lab §4.2: cambia un refresh token por otro y por un access token nuevo.

    Rotar va primero porque el usuario sale del registro del token. Después se relee la cuenta:
    una inactiva, suprimida o inexistente pierde la sesión. Una renovación correcta no deja fila
    en la bitácora (sería una cada 15 minutos por usuario); un token ya rotado sí, en su propia
    transacción. Los demás rechazos los audita el router, como en el logout.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        tokens: TokenService,
        sesiones: SesionesRenovacion,
        registrar: RegistrarAccesoDenegado,
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._sesiones = sesiones
        self._registrar = registrar

    async def execute(self, refresh_token: str, ip_origen: str | None) -> SesionRenovada:
        resultado = await self._sesiones.rotar(refresh_token)
        if isinstance(resultado, RotacionInvalida):
            raise TokenInvalidoError(motivo="invalido")
        if isinstance(resultado, RotacionRevocada):
            raise TokenInvalidoError(motivo="revocado", usuario_id=resultado.usuario_id)
        if not isinstance(resultado, RotacionOk):
            await self._registrar.execute(
                resultado.usuario_id,
                ip_origen,
                {"familia": resultado.familia},
                accion="REFRESH_REUTILIZADO",
            )
            raise TokenInvalidoError(motivo="reutilizado", usuario_id=resultado.usuario_id)

        usuario: Usuario | None = None
        token: TokenEmitido | None = None
        try:
            async with self._uow as uow:
                usuario = await uow.usuarios.find_by_id(resultado.usuario_id)
                if usuario is not None and usuario.activo and not usuario.suprimido:
                    # Sin await desde la lectura: el token lleva el rol de ahora (C-21, C-53).
                    token = self._tokens.emitir(usuario, sid=resultado.familia)
        except Exception as exc:
            await self._revocar_tras_fallo(resultado.familia, exc)
            raise ServicioNoDisponibleError() from exc

        if usuario is None or token is None:
            await self._sesiones.revocar_familia(resultado.familia)
            # Sin fila no hay usuario que atribuir: la bitácora tiene una llave foránea.
            raise TokenInvalidoError(
                motivo="revocado", usuario_id=usuario.id if usuario is not None else None
            )
        return SesionRenovada(token=token, usuario=usuario, rotacion=resultado)

    async def _revocar_tras_fallo(self, familia: str, causa: Exception) -> None:
        # El token presentado ya se rotó y el nuevo no llegará al cliente. Sin esto, su reintento
        # dejaría una fila de robo falsa (C-60).
        logger.error("No se pudo releer la cuenta al renovar la sesión: %s", type(causa).__name__)
        try:
            await self._sesiones.revocar_familia(familia)
        except ServicioNoDisponibleError:
            logger.error("Tampoco se pudo revocar la familia tras el fallo")
