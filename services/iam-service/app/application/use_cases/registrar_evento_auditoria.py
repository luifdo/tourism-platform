import ipaddress
from collections.abc import Callable
from dataclasses import replace

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.evento_auditoria import EventoAuditoria


class RegistrarEventoAuditoria:
    """Guarda en la bitácora un `auditoria.registrada` de otro servicio (UC33, RNF-10).

    Recibe una fábrica de UnitOfWork, no una instancia: el worker procesa varios mensajes a
    la vez y cada uno necesita su propia transacción.

    La idempotencia la da la base (`UNIQUE(event_id)`, C-04). Un `ip_origen` que no es una IP
    no descarta el evento: se guarda nulo y su texto queda en `detalles.ip_origen_invalida`
    (C-38). Los errores de la base se propagan para que el consumidor reintente.
    """

    def __init__(self, uow: Callable[[], UnitOfWork]) -> None:
        self._uow = uow

    async def execute(self, evento: EventoAuditoria) -> ResultadoConsumo:
        evento = _con_ip_valida(evento)
        async with self._uow() as uow:
            insertado = await uow.auditoria.registrar_evento(evento)
            await uow.commit()
        return ResultadoConsumo.APLICADO if insertado else ResultadoConsumo.DUPLICADO


def _con_ip_valida(evento: EventoAuditoria) -> EventoAuditoria:
    if evento.ip_origen is None or _es_ip(evento.ip_origen):
        return evento
    return replace(
        evento,
        ip_origen=None,
        detalles={**evento.detalles, "ip_origen_invalida": evento.ip_origen},
    )


def _es_ip(texto: str) -> bool:
    """Una IP suelta que acepte el tipo INET: sin máscara (`/8`) ni zona IPv6 (`%eth0`)."""
    try:
        ip = ipaddress.ip_address(texto)
    except ValueError:
        return False
    return getattr(ip, "scope_id", None) is None
