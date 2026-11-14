from datetime import datetime

from app.application.dto.servicio_editable import ServicioEditable
from app.application.ports.consulta_prestador import ConsultaPrestador
from app.application.ports.invalidador_cache import InvalidadorCache
from app.domain.entities.atractivo_servicio import AtractivoServicio
from app.domain.events.servicio_publicado import ServicioPublicado
from app.domain.ports.unidad_de_trabajo import UnidadDeTrabajo


class EscrituraServicio:
    """Pasos comunes al guardar un cambio de un servicio (UC17, UC18).

    1. La zona se recalcula con PostGIS según la ubicación.
    2. El servicio y `servicio.publicado` se guardan en la misma transacción (outbox).
    3. Tras confirmar se invalida la caché de búsqueda y mapa, y se relee el resultado.
    """

    def __init__(self, consulta: ConsultaPrestador, invalidador: InvalidadorCache) -> None:
        self._consulta = consulta
        self._invalidador = invalidador

    async def guardar_y_publicar(
        self, uow: UnidadDeTrabajo, servicio: AtractivoServicio, ahora: datetime
    ) -> None:
        servicio.asignar_zona(await uow.zonas.zona_de(servicio.datos.ubicacion))
        await uow.servicios.guardar(servicio)
        await uow.outbox.agregar(ServicioPublicado.de(servicio, ahora))

    async def despues_de_confirmar(self, servicio: AtractivoServicio) -> ServicioEditable:
        await self._invalidador.invalidar()
        return await self.leer(servicio)

    async def leer(self, servicio: AtractivoServicio) -> ServicioEditable:
        editable = await self._consulta.servicio(servicio.id)
        if editable is None:  # no ocurre: el servicio se acaba de confirmar y no se borra
            raise RuntimeError(f"Servicio {servicio.id} no encontrado tras guardarlo")
        return editable
