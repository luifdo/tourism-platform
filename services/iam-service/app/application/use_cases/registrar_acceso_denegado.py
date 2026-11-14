import logging
import uuid
from typing import Any

from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import ResultadoAuditoria

logger = logging.getLogger(__name__)


class RegistrarAccesoDenegado:
    """Audita un 401/403 en su propia transacción (RNF-10, ESC-04): ACCESS_DENIED, salvo que se
    indique otra acción (REFRESH_REUTILIZADO, C-20).

    Nunca propaga errores: si la bitácora falla, el rechazo sigue siendo 401/403, no un 500.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        usuario_id: uuid.UUID | None,
        ip_origen: str | None,
        detalles: dict[str, Any],
        accion: str = "ACCESS_DENIED",
    ) -> None:
        try:
            async with self._uow as uow:
                await uow.auditoria.registrar(
                    accion=accion,
                    resultado=ResultadoAuditoria.DENEGADO,
                    usuario_id=usuario_id,
                    ip_origen=ip_origen,
                    detalles=detalles,
                )
                await uow.commit()
        except Exception as exc:
            # Sin detalles ni token en el log: solo el tipo de error y el motivo.
            logger.error(
                "No se pudo registrar %s (%s): %s",
                accion,
                detalles.get("motivo", "rol"),
                type(exc).__name__,
            )
