from app.application.dto.servicio_pendiente import ServicioPendiente
from app.application.ports.consulta_resenas import ConsultaResenas
from app.domain.value_objects.identidad import Identidad, Rol


class ListarPendientes:
    """Servicios que el turista puede reseñar: con reserva finalizada y sin reseña suya.
    El nombre del servicio lo toma la PWA del catálogo."""

    def __init__(self, consulta: ConsultaResenas) -> None:
        self._consulta = consulta

    async def execute(self, identidad: Identidad) -> list[ServicioPendiente]:
        identidad.exigir_rol(Rol.TURISTA)
        return await self._consulta.pendientes(identidad.usuario_id)
