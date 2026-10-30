"""Calendario de cupos y tarifas del prestador (UC19) y consulta pública de disponibilidad (UC10)."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from application.base import Contexto, eventos_de_dias
from application.errores import DiaExistente, NoEncontrado, VersionDistinta
from application.ports import UnidadDeTrabajo
from domain.disponibilidad import DisponibilidadCupo
from domain.errores import Validacion
from domain.reglas import hoy_local
from domain.servicio import ServicioRef

MAX_DIAS_CONSULTA = 62
MAX_DIAS_RANGO = 366


def validar_rango(desde: date, hasta: date, maximo: int) -> None:
    if hasta < desde:
        raise Validacion("`hasta` no puede ser anterior a `desde`.")
    if (hasta - desde).days > maximo:
        raise Validacion(f"El rango admite máximo {maximo} días.")


async def _servicio_del_prestador(
    uow: UnidadDeTrabajo, servicio_id: UUID, prestador_usuario_id: UUID, para_escribir: bool
) -> ServicioRef:
    """El dueño sale de `servicio_ref`. Para no revelar servicios ajenos, todo es 404."""
    servicio = await uow.servicios.leer(servicio_id)
    if servicio is None or not servicio.es_de(prestador_usuario_id):
        raise NoEncontrado("El servicio no existe o no le pertenece.")
    if para_escribir:
        servicio.exigir_activo()
    return servicio


class ConsultarDisponibilidad:
    """UC10: días de un servicio en un rango. Un servicio inactivo o desconocido no muestra días."""

    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(self, servicio_id: UUID, desde: date, hasta: date) -> list[DisponibilidadCupo]:
        validar_rango(desde, hasta, MAX_DIAS_CONSULTA)
        async with self.ctx.uow() as uow:
            servicio = await uow.servicios.leer(servicio_id)
            if servicio is None or not servicio.activo:
                return []
            return await uow.disponibilidad.rango(servicio_id, desde, hasta)


class ConsultarCalendario:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(
        self, prestador_usuario_id: UUID, servicio_id: UUID, desde: date, hasta: date
    ) -> list[DisponibilidadCupo]:
        validar_rango(desde, hasta, MAX_DIAS_RANGO)
        async with self.ctx.uow() as uow:
            await _servicio_del_prestador(uow, servicio_id, prestador_usuario_id, para_escribir=False)
            return await uow.disponibilidad.rango(servicio_id, desde, hasta)


class AbrirRangoCalendario:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(
        self,
        prestador_usuario_id: UUID,
        servicio_id: UUID,
        desde: date,
        hasta: date,
        cupos_totales: int,
        tarifa_dia: Decimal | None = None,
        dias_semana: set[int] | None = None,
    ) -> tuple[list[date], list[date]]:
        validar_rango(desde, hasta, MAX_DIAS_RANGO)
        if desde < hoy_local(self.ctx.reloj.ahora()):
            raise Validacion("No se pueden abrir días pasados.")
        if dias_semana and not dias_semana <= set(range(1, 8)):
            raise Validacion("Los días de la semana van de 1 (lunes) a 7 (domingo).")
        creados: list[DisponibilidadCupo] = []
        omitidos: list[date] = []
        async with self.ctx.uow() as uow:
            servicio = await _servicio_del_prestador(uow, servicio_id, prestador_usuario_id, para_escribir=True)
            fecha = desde
            while fecha <= hasta:
                if not dias_semana or fecha.isoweekday() in dias_semana:
                    if await uow.disponibilidad.obtener_para_cambiar(servicio_id, fecha):
                        omitidos.append(fecha)
                    else:
                        dia = DisponibilidadCupo.abrir(
                            servicio_id, fecha, cupos_totales, tarifa_dia,
                            aforo=servicio.capacidad_aforo_diario,
                        )
                        await uow.disponibilidad.guardar(dia)
                        creados.append(dia)
                fecha += timedelta(days=1)
            await uow.outbox.agregar(eventos_de_dias(creados), None)
            await uow.commit()
        return [d.fecha for d in creados], omitidos


class GuardarDiaCalendario:
    """PUT de un día: sin versión solo crea; con versión edita si coincide."""

    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(
        self,
        prestador_usuario_id: UUID,
        servicio_id: UUID,
        fecha: date,
        cupos_totales: int,
        tarifa_dia: Decimal | None,
        version_esperada: int | None,
    ) -> tuple[DisponibilidadCupo, bool]:
        if fecha < hoy_local(self.ctx.reloj.ahora()):
            raise Validacion("No se pueden editar días pasados.")
        async with self.ctx.uow() as uow:
            servicio = await _servicio_del_prestador(uow, servicio_id, prestador_usuario_id, para_escribir=True)
            aforo = servicio.capacidad_aforo_diario
            dia = await uow.disponibilidad.obtener_para_cambiar(servicio_id, fecha)
            creado = dia is None
            if dia is None:
                if version_esperada is not None:
                    raise NoEncontrado("El día no existe; envíelo sin If-Match para crearlo.")
                dia = DisponibilidadCupo.abrir(servicio_id, fecha, cupos_totales, tarifa_dia, aforo)
            else:
                if version_esperada is None:
                    raise DiaExistente("El día ya existe; envíe If-Match con su versión para editarlo.")
                if dia.version != version_esperada:
                    raise VersionDistinta("El día cambió en el servidor.", dia)
                dia.ajustar(cupos_totales, tarifa_dia, aforo)
            await uow.disponibilidad.guardar(dia)
            await uow.outbox.agregar(eventos_de_dias([dia]), None)
            await uow.commit()
        return dia, creado
