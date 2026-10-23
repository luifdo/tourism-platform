"""Tareas programadas (CronJobs `expirar-solicitudes` y `finalizar-reservas`, Guía §6.4)."""

from application.base import Contexto, eventos_de, eventos_de_dias
from domain.disponibilidad import DisponibilidadCupo
from domain.reglas import hoy_local
from domain.eventos import EventoDominio

LOTE = 100


class ExpirarSolicitudes:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(self) -> int:
        ahora = self.ctx.reloj.ahora()
        total = 0
        while True:
            eventos: list[EventoDominio] = []
            dias: list[DisponibilidadCupo] = []
            async with self.ctx.uow() as uow:
                lote = await uow.reservas.solicitudes_vencidas(ahora, LOTE)
                for reserva in lote:
                    reserva.expirar(ahora)
                    dia = await uow.disponibilidad.obtener_para_cambiar(reserva.servicio_id, reserva.fecha_reserva)
                    if dia is not None:
                        dia.liberar(reserva.numero_personas)
                        await uow.disponibilidad.guardar(dia)
                        dias.append(dia)
                    await uow.reservas.guardar(reserva)
                    eventos += eventos_de(reserva, None)
                await uow.commit()
            # Un solo evento por día, con su estado final, aunque el lote haya tocado el día varias veces.
            await self.ctx.publicador.publicar(eventos + eventos_de_dias(dias), None)
            total += len(lote)
            if len(lote) < LOTE:
                return total


class FinalizarReservas:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(self) -> int:
        ahora = self.ctx.reloj.ahora()
        total = 0
        while True:
            eventos: list[EventoDominio] = []
            async with self.ctx.uow() as uow:
                lote = await uow.reservas.por_finalizar(hoy_local(ahora), LOTE)
                for reserva in lote:
                    reserva.finalizar(ahora)
                    await uow.reservas.guardar(reserva)
                    eventos += eventos_de(reserva, None)
                await uow.commit()
            await self.ctx.publicador.publicar(eventos, None)
            total += len(lote)
            if len(lote) < LOTE:
                return total
