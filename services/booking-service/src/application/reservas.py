"""Casos de uso del ciclo de vida de la reserva (UC11, UC12, UC20).

Patrón común: abrir transacción, bloquear filas, aplicar la regla de dominio,
COMMIT y, solo después, publicar los eventos (Guía §2 y §6).
"""

from datetime import date
from uuid import UUID

from application.base import Contexto, eventos_de
from application.errores import NoEncontrado, ReservaDuplicada, VersionDistinta
from application.ports import UnidadDeTrabajo
from domain.disponibilidad import DisponibilidadCupo
from domain.errores import NoDisponible
from domain.reserva import Actor, Reserva
from domain.servicio import ServicioRef


async def _servicio_activo(uow: UnidadDeTrabajo, servicio_id: UUID) -> ServicioRef:
    servicio = await uow.servicios.leer(servicio_id)
    if servicio is None:
        raise NoEncontrado("El servicio no existe.")
    servicio.exigir_activo()
    return servicio


async def _dia(uow: UnidadDeTrabajo, servicio_id: UUID, fecha: date) -> DisponibilidadCupo:
    dia = await uow.disponibilidad.obtener_para_cambiar(servicio_id, fecha)
    if dia is None:
        raise NoDisponible(f"El servicio no tiene cupos habilitados el {fecha.isoformat()}.")
    return dia


async def _reserva_de(uow: UnidadDeTrabajo, reserva_id: UUID, actor: Actor, usuario_id: UUID) -> Reserva:
    """La reserva solo existe para su turista o para el prestador dueño (404 en otro caso)."""
    reserva = await uow.reservas.obtener_para_cambiar(reserva_id)
    if reserva is None:
        raise NoEncontrado("La reserva no existe.")
    duenio = reserva.turista_id if actor is Actor.TURISTA else reserva.prestador_usuario_id
    if duenio != usuario_id:
        raise NoEncontrado("La reserva no existe.")
    return reserva


async def _liberar(uow: UnidadDeTrabajo, reserva: Reserva) -> DisponibilidadCupo | None:
    dia = await uow.disponibilidad.obtener_para_cambiar(reserva.servicio_id, reserva.fecha_reserva)
    if dia is not None:
        dia.liberar(reserva.numero_personas)
        await uow.disponibilidad.guardar(dia)
    return dia


class SolicitarReserva:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(
        self,
        turista_id: UUID,
        servicio_id: UUID,
        fecha_reserva: date,
        numero_personas: int,
        correlation_id: str | None = None,
    ) -> Reserva:
        ahora = self.ctx.reloj.ahora()
        async with self.ctx.uow() as uow:
            servicio = await _servicio_activo(uow, servicio_id)
            dia = await _dia(uow, servicio_id, fecha_reserva)
            if await uow.reservas.existe_activa(turista_id, servicio_id, fecha_reserva):
                raise ReservaDuplicada(
                    "Ya tiene una reserva activa para ese servicio y fecha; modifíquela."
                )
            reserva = Reserva.solicitar(
                servicio, turista_id, fecha_reserva, numero_personas, ahora, self.ctx.plazo_horas
            )
            dia.descontar(numero_personas)
            await uow.disponibilidad.guardar(dia)
            await uow.reservas.guardar(reserva)
            await uow.commit()
        await self.ctx.publicador.publicar(eventos_de(reserva, turista_id, [dia]), correlation_id)
        return reserva


class ModificarReserva:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(
        self,
        turista_id: UUID,
        reserva_id: UUID,
        version_esperada: int,
        fecha_reserva: date | None = None,
        numero_personas: int | None = None,
        correlation_id: str | None = None,
    ) -> Reserva:
        ahora = self.ctx.reloj.ahora()
        async with self.ctx.uow() as uow:
            reserva = await _reserva_de(uow, reserva_id, Actor.TURISTA, turista_id)
            if reserva.version != version_esperada:
                raise VersionDistinta("La reserva cambió mientras la editaba.", reserva.version)
            await _servicio_activo(uow, reserva.servicio_id)

            fecha_anterior, personas_anterior = reserva.fecha_reserva, reserva.numero_personas
            reserva.modificar(ahora, fecha_reserva, numero_personas, self.ctx.plazo_horas)

            if reserva.fecha_reserva != fecha_anterior and await uow.reservas.existe_activa(
                turista_id, reserva.servicio_id, reserva.fecha_reserva, excluir=reserva.id
            ):
                raise ReservaDuplicada("Ya tiene otra reserva activa para esa fecha.")

            # Bloqueo en orden ascendente de fecha para evitar interbloqueos (Guía §6.1).
            fechas = sorted({fecha_anterior, reserva.fecha_reserva})
            dias = {f: await _dia(uow, reserva.servicio_id, f) for f in fechas}
            dias[fecha_anterior].liberar(personas_anterior)
            dias[reserva.fecha_reserva].descontar(reserva.numero_personas)
            for dia in dias.values():
                await uow.disponibilidad.guardar(dia)
            await uow.reservas.guardar(reserva)
            await uow.commit()
        await self.ctx.publicador.publicar(eventos_de(reserva, turista_id, dias.values()), correlation_id)
        return reserva


class ConfirmarReserva:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(self, prestador_usuario_id: UUID, reserva_id: UUID, correlation_id: str | None = None) -> Reserva:
        async with self.ctx.uow() as uow:
            reserva = await _reserva_de(uow, reserva_id, Actor.PRESTADOR, prestador_usuario_id)
            reserva.confirmar(self.ctx.reloj.ahora())
            await uow.reservas.guardar(reserva)
            await uow.commit()
        await self.ctx.publicador.publicar(eventos_de(reserva, prestador_usuario_id), correlation_id)
        return reserva


class RechazarReserva:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(
        self, prestador_usuario_id: UUID, reserva_id: UUID, motivo: str, correlation_id: str | None = None
    ) -> Reserva:
        async with self.ctx.uow() as uow:
            reserva = await _reserva_de(uow, reserva_id, Actor.PRESTADOR, prestador_usuario_id)
            reserva.rechazar(motivo, self.ctx.reloj.ahora())
            dia = await _liberar(uow, reserva)
            await uow.reservas.guardar(reserva)
            await uow.commit()
        await self.ctx.publicador.publicar(eventos_de(reserva, prestador_usuario_id, [dia]), correlation_id)
        return reserva


class CancelarReserva:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(
        self,
        actor: Actor,
        usuario_id: UUID,
        reserva_id: UUID,
        motivo: str | None = None,
        correlation_id: str | None = None,
    ) -> Reserva:
        async with self.ctx.uow() as uow:
            reserva = await _reserva_de(uow, reserva_id, actor, usuario_id)
            reserva.cancelar(actor, self.ctx.reloj.ahora(), motivo)
            dia = await _liberar(uow, reserva)
            await uow.reservas.guardar(reserva)
            await uow.commit()
        await self.ctx.publicador.publicar(eventos_de(reserva, usuario_id, [dia]), correlation_id)
        return reserva
