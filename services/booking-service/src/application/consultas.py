"""Consultas de reservas (UC13 y panel del prestador, UC20)."""

from uuid import UUID

from application.base import Contexto
from application.errores import NoEncontrado
from application.ports import FiltroReservas
from domain.reserva import Reserva


class ListarReservas:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(self, filtro: FiltroReservas, pagina: int, tamano: int) -> tuple[list[Reserva], int]:
        async with self.ctx.uow() as uow:
            return await uow.reservas.listar(filtro, pagina, tamano)


class ObtenerReserva:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(self, usuario_id: UUID, reserva_id: UUID) -> Reserva:
        async with self.ctx.uow() as uow:
            reserva = await uow.reservas.leer(reserva_id)  # GET: sin bloqueo
        if reserva is None or usuario_id not in (reserva.turista_id, reserva.prestador_usuario_id):
            raise NoEncontrado("La reserva no existe.")
        return reserva
