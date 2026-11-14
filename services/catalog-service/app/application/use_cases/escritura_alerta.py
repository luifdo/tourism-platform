from datetime import datetime

from app.application.dto.alerta_editable import AlertaEditable
from app.domain.entities.alerta_oficial import AlertaOficial
from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.domain.ports.unidad_de_trabajo import UnidadDeTrabajo
from app.domain.value_objects.identidad import Identidad


class EscrituraAlerta:
    """Pasos comunes al guardar un cambio de una alerta oficial (UC26).

    La alerta y `auditoria.registrada` se guardan en la misma transacción (outbox). No se
    invalida la caché: las alertas no se cachean en ningún lado, deben verse al instante.
    """

    async def guardar_y_auditar(
        self,
        uow: UnidadDeTrabajo,
        alerta: AlertaOficial,
        zona_codigo: str | None,
        identidad: Identidad,
        accion: str,
        ahora: datetime,
    ) -> AlertaEditable:
        await uow.alertas.guardar(alerta)
        destino = {"zona": zona_codigo} if zona_codigo else {"servicio_id": str(alerta.servicio_id)}
        await uow.outbox.agregar(
            AuditoriaRegistrada(
                usuario_id=identidad.usuario_id,
                accion=accion,
                detalles={
                    "alerta_id": str(alerta.id),
                    "nivel": alerta.nivel.value,
                    "fecha_expiracion": alerta.fecha_expiracion.isoformat(),
                    "version": alerta.version,
                }
                | destino,
                ocurrido_en=ahora,
            )
        )
        return AlertaEditable(alerta, zona_codigo)

    async def zona_de(self, uow: UnidadDeTrabajo, alerta: AlertaOficial) -> str | None:
        if alerta.zona_id is None:
            return None
        zona = await uow.zonas.obtener(alerta.zona_id)
        return zona.codigo.valor if zona else None
