from datetime import datetime
from typing import Any

from app.application.ports.invalidador_cache import InvalidadorCache
from app.domain.entities.zona import Zona
from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.domain.ports.unidad_de_trabajo import UnidadDeTrabajo
from app.domain.value_objects.identidad import Identidad


class EscrituraZona:
    """Pasos comunes al guardar un cambio de una zona (Entidad y Admin).

    1. Si cambió el área que cubre la zona (creada, polígono nuevo o desactivada), PostGIS
       recalcula la zona de los servicios afectados en la misma transacción.
    2. `auditoria.registrada` se guarda en el outbox con el cambio.
    3. Tras confirmar se invalida la caché: búsqueda y mapa muestran la zona de cada servicio.
    """

    def __init__(self, invalidador: InvalidadorCache) -> None:
        self._invalidador = invalidador

    async def guardar_y_auditar(
        self,
        uow: UnidadDeTrabajo,
        zona: Zona,
        identidad: Identidad,
        accion: str,
        ahora: datetime,
        reasignar: bool,
        **detalles: Any,
    ) -> None:
        await uow.zonas.guardar(zona)
        if reasignar:
            await uow.zonas.reasignar_servicios(zona.id)
        await uow.outbox.agregar(
            AuditoriaRegistrada(
                usuario_id=identidad.usuario_id,
                accion=accion,
                detalles={
                    "zona_id": str(zona.id),
                    "codigo": zona.codigo.valor,
                    "version": zona.version,
                }
                | detalles,
                ocurrido_en=ahora,
            )
        )

    async def despues_de_confirmar(self) -> None:
        await self._invalidador.invalidar()
