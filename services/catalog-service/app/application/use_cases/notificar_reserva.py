import logging
from uuid import UUID

from app.application.dto.datos_correo_reserva import DatosCorreoReserva
from app.application.dto.plantilla_correo import PlantillaCorreo
from app.application.dto.reserva_notificada import ReservaNotificada
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.ports.consulta_prestador import ConsultaPrestador
from app.application.ports.directorio_usuarios import DirectorioUsuarios
from app.application.ports.enviador_correo import EnviadorCorreo
from app.application.ports.redactor_correos import RedactorCorreos
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.domain.entities.reserva_proyeccion import TipoEventoReserva
from app.domain.value_objects.identidad import Rol

logger = logging.getLogger(__name__)

CONSUMIDOR = "catalog.notificaciones"

_T = TipoEventoReserva
_PLANTILLA = {
    _T.SOLICITADA: PlantillaCorreo.SOLICITUD,
    _T.MODIFICADA: PlantillaCorreo.MODIFICACION,
    _T.CONFIRMADA: PlantillaCorreo.CONFIRMACION,
    _T.RECHAZADA: PlantillaCorreo.RECHAZO,
    _T.CANCELADA: PlantillaCorreo.CANCELACION,
}


class NotificarReserva:
    """Correos de reservas (UC36 y avisos al prestador).

    * Solicitada y modificada → al prestador; confirmada y rechazada → al turista; cancelada
      → a la otra parte (según `cancelada_por`). Finalizada no envía correo.
    * El contacto se pide a iam al momento (Plan §4.1, excepción de contacto) y no se guarda.
    * Un correo no es transaccional: se revisa si el evento ya se procesó, se envía y luego
      se registra. Si el worker cae entre el envío y el registro, el correo sale dos veces;
      se prefiere eso a perderlo.
    """

    def __init__(
        self,
        unidad_de_trabajo: FabricaUnidadDeTrabajo,
        catalogo: ConsultaPrestador,
        directorio: DirectorioUsuarios,
        redactor: RedactorCorreos,
        enviador: EnviadorCorreo,
    ) -> None:
        self._uow = unidad_de_trabajo
        self._catalogo = catalogo
        self._directorio = directorio
        self._redactor = redactor
        self._enviador = enviador

    async def execute(self, reserva: ReservaNotificada) -> ResultadoConsumo:
        plantilla = _PLANTILLA.get(reserva.tipo)
        if plantilla is None:
            return ResultadoConsumo.IGNORADO
        async with self._uow() as uow:
            if await uow.eventos_procesados.ya_procesado(reserva.event_id, CONSUMIDOR):
                return ResultadoConsumo.DUPLICADO
        resultado = await self._enviar(plantilla, reserva)
        async with self._uow() as uow:
            await uow.eventos_procesados.registrar(reserva.event_id, CONSUMIDOR)
            await uow.confirmar()
        return resultado

    async def _enviar(
        self, plantilla: PlantillaCorreo, reserva: ReservaNotificada
    ) -> ResultadoConsumo:
        editable = await self._catalogo.servicio(reserva.servicio_id)
        if editable is None:
            logger.warning("Correo de %s sin servicio %s", reserva.tipo, reserva.servicio_id)
            return ResultadoConsumo.IGNORADO
        servicio = editable.servicio
        perfil = await self._catalogo.perfil_de_usuario(servicio.prestador_usuario_id)
        if perfil is None:
            logger.warning("Correo de %s sin perfil de prestador", reserva.tipo)
            return ResultadoConsumo.IGNORADO

        por_turista = reserva.cancelada_por is Rol.TURISTA
        destinatario_id = self._destinatario(plantilla, reserva, servicio.prestador_usuario_id)
        contacto = await self._directorio.contacto(destinatario_id)
        if contacto is None:
            logger.warning("Usuario %s sin contacto en iam: no se envía", destinatario_id)
            return ResultadoConsumo.IGNORADO

        correo = self._redactor.redactar(
            plantilla,
            DatosCorreoReserva(
                destinatario=contacto,
                servicio=servicio.datos.nombre,
                fecha_reserva=reserva.fecha_reserva,
                numero_personas=reserva.numero_personas,
                prestador=perfil,
                pagos=servicio.datos.atributos.pagos,
                motivo=reserva.motivo,
                cancelada_por_turista=por_turista,
                fecha_anterior=reserva.fecha_anterior,
                numero_personas_anterior=reserva.numero_personas_anterior,
                expira_en=reserva.expira_en,
            ),
        )
        await self._enviador.enviar(correo)
        return ResultadoConsumo.APLICADO

    @staticmethod
    def _destinatario(
        plantilla: PlantillaCorreo, reserva: ReservaNotificada, prestador_usuario_id: UUID
    ) -> UUID:
        if plantilla in (PlantillaCorreo.SOLICITUD, PlantillaCorreo.MODIFICACION):
            return prestador_usuario_id
        if plantilla is PlantillaCorreo.CANCELACION and reserva.cancelada_por is Rol.TURISTA:
            return prestador_usuario_id  # canceló el turista: se avisa al prestador
        return reserva.turista_id
