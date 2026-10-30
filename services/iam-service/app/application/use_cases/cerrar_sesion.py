import uuid

from app.application.use_cases.verificar_acceso import VerificarAcceso
from app.domain.ports.revocacion_tokens import RevocacionTokens
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import ResultadoAuditoria


class CerrarSesion:
    """UC2: cierre de sesión. Revoca el token por su jti hasta que expire."""

    def __init__(
        self, uow: UnitOfWork, verificar: VerificarAcceso, revocacion: RevocacionTokens
    ) -> None:
        self._uow = uow
        self._verificar = verificar
        self._revocacion = revocacion

    async def execute(self, token: str | None, ip_origen: str | None) -> None:
        # Mismas reglas que el ForwardAuth (incluida la revocación por usuario).
        claims = await self._verificar.execute(token)

        # Primero se revoca: si la bitácora fallara, el token ya no sirve (lo seguro).
        await self._revocacion.revocar(claims.jti, claims.exp)
        async with self._uow as uow:
            await uow.auditoria.registrar(
                accion="LOGOUT",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=uuid.UUID(claims.sub),
                ip_origen=ip_origen,
                detalles={},
            )
            await uow.commit()
