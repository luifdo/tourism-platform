from uuid import UUID

from app.domain.entities.resena import Resena
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj
from app.domain.ports.unidad_de_trabajo import FabricaUnidadDeTrabajo
from app.domain.value_objects.identidad import Identidad, Rol


class ResponderResena:
    """UC21: el prestador dueño del servicio responde públicamente una reseña.

    Una respuesta por reseña: esta operación la crea o la reemplaza (`If-Match`). El dueño
    sale de la proyección de `servicio.publicado`. En revisión se puede responder (es la
    forma de que el prestador dé su versión); oculta, no. No publica eventos: la respuesta no
    cambia el promedio.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._uow = unidad_de_trabajo
        self._reloj = reloj

    async def execute(
        self, identidad: Identidad, resena_id: UUID, version_esperada: int, texto: str
    ) -> Resena:
        identidad.exigir_rol(Rol.PRESTADOR)
        async with self._uow() as uow:
            resena = await uow.resenas.obtener(resena_id)
            if resena is None:
                raise NoEncontrado(resena=str(resena_id))
            dueno = await uow.servicios.obtener(resena.servicio_id)
            resena.responder(
                identidad.usuario_id, dueno, version_esperada, texto, self._reloj.ahora()
            )
            await uow.resenas.guardar(resena)
            await uow.confirmar()
        return resena
