"""Proyección `servicio_ref` desde el evento `servicio.publicado.v1` del catálogo."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from application.base import Contexto
from domain.servicio import ServicioRef


def servicio_desde_evento(payload: dict[str, Any]) -> ServicioRef:
    return ServicioRef(
        servicio_id=UUID(payload["servicio_id"]),
        prestador_id=UUID(payload["prestador_id"]),
        prestador_usuario_id=UUID(payload["prestador_usuario_id"]),
        capacidad_aforo_diario=int(payload["capacidad_aforo_diario"]),
        tarifa_base=Decimal(str(payload["tarifa_base"])),
        activo=bool(payload["activo"]),
        version=int(payload["version"]),
    )


class AplicarServicioPublicado:
    """Guarda el servicio solo si el evento es más nuevo; devuelve si se aplicó."""

    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    async def __call__(self, payload: dict[str, Any]) -> bool:
        nuevo = servicio_desde_evento(payload)
        async with self.ctx.uow() as uow:
            # La comparación de versiones la hace el repositorio en el mismo paso que guarda:
            # leer y luego guardar dejaba una ventana en la que dos eventos se pisaban.
            aplicado = await uow.servicios.guardar_si_mas_nuevo(nuevo)
            if aplicado:
                await uow.commit()
        return aplicado
