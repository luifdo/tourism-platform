"""Eventos de auditoría que no acompañan ningún cambio de datos."""

from uuid import UUID

from application.base import Contexto, evento_auditoria


class RegistrarAccesoDenegado:
    """ESC-04: todo acceso denegado por rol queda en la bitácora del Módulo 1.

    No hay cambio de datos que acompañar, así que usa su propia transacción solo para el outbox.
    """

    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(self, usuario_id: UUID, ruta: str, rol: str, correlation_id: str | None) -> None:
        evento = evento_auditoria(usuario_id, "ACCESS_DENIED", "DENEGADO", ruta=ruta, rol=rol)
        async with self.ctx.uow() as uow:
            await uow.outbox.agregar([evento], correlation_id)
            await uow.commit()
