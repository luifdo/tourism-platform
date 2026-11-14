import logging
import uuid
from typing import Any

from app.domain.exceptions import RangoFechasInvalidoError
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import ResultadoAuditoria
from app.domain.value_objects.filtro_bitacora import FiltroBitacora, PaginaBitacora

logger = logging.getLogger(__name__)


class ConsultarBitacora:
    """UC33: el Admin consulta la bitácora de auditoría (RNF-10), de la más reciente a la más
    antigua.

    Cada consulta deja una fila `AUDIT_VIEW` con los filtros y la página (nunca los
    resultados), en su propia transacción y después de leer (C-43). Si esa escritura falla,
    solo queda un log de error: la consulta responde igual.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, filtro: FiltroBitacora, admin_id: uuid.UUID, ip_origen: str | None
    ) -> PaginaBitacora:
        if filtro.desde and filtro.hasta and filtro.desde >= filtro.hasta:
            raise RangoFechasInvalidoError()
        async with self._uow as uow:
            pagina = await uow.auditoria.listar(filtro)
        await self._registrar_consulta(filtro, admin_id, ip_origen)
        return pagina

    async def _registrar_consulta(
        self, filtro: FiltroBitacora, admin_id: uuid.UUID, ip_origen: str | None
    ) -> None:
        try:
            async with self._uow as uow:
                await uow.auditoria.registrar(
                    accion="AUDIT_VIEW",
                    resultado=ResultadoAuditoria.EXITO,
                    usuario_id=admin_id,
                    ip_origen=ip_origen,
                    detalles=_detalles(filtro),
                )
                await uow.commit()
        except Exception as exc:
            logger.error("No se pudo registrar AUDIT_VIEW: %s", type(exc).__name__)


def _detalles(filtro: FiltroBitacora) -> dict[str, Any]:
    """Solo los filtros que se usaron, en texto, más la página pedida."""
    filtros: dict[str, Any] = {
        "usuario_id": str(filtro.usuario_id) if filtro.usuario_id else None,
        "accion": filtro.accion,
        "resultado": filtro.resultado.value if filtro.resultado else None,
        "servicio_origen": filtro.servicio_origen,
        "desde": filtro.desde.isoformat() if filtro.desde else None,
        "hasta": filtro.hasta.isoformat() if filtro.hasta else None,
    }
    return {
        "filtros": {clave: valor for clave, valor in filtros.items() if valor is not None},
        "pagina": filtro.pagina,
        "tamano": filtro.tamano,
    }
