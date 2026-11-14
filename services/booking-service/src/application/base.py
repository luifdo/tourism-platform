"""Dependencias comunes de los casos de uso."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from application.ports import FabricaUnidadDeTrabajo, Reloj
from domain.reglas import PLAZO_RESPUESTA_HORAS
from domain.disponibilidad import DisponibilidadCupo
from domain.eventos import EventoDominio
from domain.reserva import Reserva


@dataclass
class Contexto:
    uow: FabricaUnidadDeTrabajo
    reloj: Reloj
    plazo_horas: int = PLAZO_RESPUESTA_HORAS


def evento_auditoria(
    usuario_id: UUID | None, accion: str, resultado: str = "EXITO", **detalles: Any
) -> EventoDominio:
    """auditoria.registrada: el Módulo 1 lo guarda en la bitácora (Plan §4.4)."""
    return EventoDominio(
        "auditoria.registrada",
        {
            "usuario_id": str(usuario_id) if usuario_id else None,
            "accion": accion,
            "resultado": resultado,
            "detalles": {k: str(v) for k, v in detalles.items()},
        },
    )


def eventos_de_dias(dias: Iterable[DisponibilidadCupo | None]) -> list[EventoDominio]:
    """Un disponibilidad.actualizada por día tocado, con su estado final.

    Si en la misma operación un día cambió varias veces (por ejemplo, un lote del CronJob que
    expira dos solicitudes del mismo día), sale un solo evento con la secuencia más alta.
    """
    finales: dict[tuple[UUID, object], DisponibilidadCupo] = {}
    for dia in dias:
        if dia is None:
            continue
        clave = (dia.servicio_id, dia.fecha)
        if clave not in finales or dia.secuencia > finales[clave].secuencia:
            finales[clave] = dia
    return [dia.evento() for dia in finales.values()]


def eventos_de(
    reserva: Reserva, usuario_id: UUID | None, dias: Iterable[DisponibilidadCupo | None] = ()
) -> list[EventoDominio]:
    """Eventos de la reserva, su registro de auditoría y la disponibilidad de los días tocados."""
    eventos = reserva.extraer_eventos()
    auditoria = [
        evento_auditoria(
            usuario_id,
            "RESERVA_" + e.tipo.split(".")[1].upper(),
            reserva_id=reserva.id,
        )
        for e in eventos
    ]
    return eventos + auditoria + eventos_de_dias(dias)
