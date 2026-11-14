import logging

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.dto.usuario_suprimido_recibido import UsuarioSuprimidoRecibido
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.application.use_cases.aplicar_prestador_aprobado import CONSUMIDOR

logger = logging.getLogger(__name__)


class AplicarUsuarioSuprimido:
    """`usuario.suprimido` (UC6, Ley 1581): borra los datos personales del perfil.

    No toca `activo` ni los servicios: si el prestador estaba visible, iam publica también
    `prestador.suspendido` en la misma transacción. Guarda el momento del evento para que un
    `prestador.aprobado` viejo que llegue después no vuelva a escribir la razón social.

    No invalida la caché: la razón social y el teléfono solo salen en el detalle del servicio,
    que no se cachea.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo) -> None:
        self._uow = unidad_de_trabajo

    async def execute(self, evento: UsuarioSuprimidoRecibido) -> ResultadoConsumo:
        async with self._uow() as uow:
            if not await uow.eventos_procesados.registrar(evento.event_id, CONSUMIDOR):
                return ResultadoConsumo.DUPLICADO
            perfil = await uow.prestadores.obtener_por_usuario(evento.usuario_id)
            if perfil is None:
                await uow.confirmar()  # queda registrado como procesado
                return ResultadoConsumo.IGNORADO
            if perfil.es_evento_iam_viejo(evento.ocurrido_en):
                logger.info("usuario.suprimido viejo para %s: se ignora", perfil.id)
                await uow.confirmar()
                return ResultadoConsumo.IGNORADO
            perfil.suprimir_datos()
            perfil.registrar_evento_iam(evento.ocurrido_en)
            await uow.prestadores.guardar(perfil)
            await uow.confirmar()
        return ResultadoConsumo.APLICADO
