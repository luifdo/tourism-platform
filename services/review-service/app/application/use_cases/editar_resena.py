from uuid import UUID

from app.domain.entities.resena import Resena
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj
from app.domain.ports.unidad_de_trabajo import FabricaUnidadDeTrabajo
from app.domain.value_objects.contenido_resena import ContenidoResena
from app.domain.value_objects.identidad import Identidad, Rol


class EditarResena:
    """UC15: el autor corrige su reseña mientras está publicada (`If-Match`).

    Publica `resena.publicada` con la puntuación nueva; la respuesta del prestador se
    conserva y el mes pasa a ser el de su visita más reciente.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._uow = unidad_de_trabajo
        self._reloj = reloj

    async def execute(
        self,
        identidad: Identidad,
        resena_id: UUID,
        version_esperada: int,
        contenido: ContenidoResena,
    ) -> Resena:
        identidad.exigir_rol(Rol.TURISTA)
        async with self._uow() as uow:
            resena = await uow.resenas.obtener(resena_id)
            if resena is None:
                raise NoEncontrado(resena=str(resena_id))
            elegibilidad = await uow.elegibilidades.obtener(resena.turista_id, resena.servicio_id)
            evento = resena.editar(
                identidad.usuario_id,
                version_esperada,
                contenido,
                elegibilidad,
                self._reloj.ahora(),
            )
            await uow.resenas.guardar(resena)
            await uow.outbox.agregar(evento)
            await uow.confirmar()
        return resena
