from uuid import UUID

from app.domain.entities.resena import Resena
from app.domain.errors import YaResenado
from app.domain.ports.reloj import Reloj
from app.domain.ports.unidad_de_trabajo import FabricaUnidadDeTrabajo
from app.domain.value_objects.contenido_resena import ContenidoResena
from app.domain.value_objects.identidad import Identidad, Rol


class EscribirResena:
    """UC15: un turista con una reserva finalizada reseña el servicio; una por servicio.

    Queda publicada al instante y `resena.publicada` se guarda en el outbox en la misma
    transacción, para que catalog recalcule el promedio.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._uow = unidad_de_trabajo
        self._reloj = reloj

    async def execute(
        self, identidad: Identidad, servicio_id: UUID, contenido: ContenidoResena
    ) -> Resena:
        identidad.exigir_rol(Rol.TURISTA)
        async with self._uow() as uow:
            # Antes que la elegibilidad: a quien ya reseñó le sirve más saber que puede editar.
            if await uow.resenas.obtener_de_turista(identidad.usuario_id, servicio_id):
                raise YaResenado(servicio=str(servicio_id))
            elegibilidad = await uow.elegibilidades.obtener(identidad.usuario_id, servicio_id)
            resena, evento = Resena.escribir(
                identidad.usuario_id, servicio_id, elegibilidad, contenido, self._reloj.ahora()
            )
            await uow.resenas.guardar(resena)  # dos envíos a la vez: el UNIQUE da YaResenado
            await uow.outbox.agregar(evento)
            await uow.confirmar()
        return resena
