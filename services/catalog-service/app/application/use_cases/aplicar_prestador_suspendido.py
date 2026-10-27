import logging

from app.application.dto.prestador_suspendido_recibido import PrestadorSuspendidoRecibido
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.ports.invalidador_cache import InvalidadorCache
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.application.use_cases.aplicar_prestador_aprobado import CONSUMIDOR
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.events.servicio_publicado import ServicioPublicado
from app.domain.ports.reloj import Reloj

logger = logging.getLogger(__name__)


class AplicarPrestadorSuspendido:
    """`prestador.suspendido` (UC27, UC28): apaga el perfil y sus servicios activos.

    Los servicios quedan marcados como desactivados por la suspensión, para restaurar solo
    esos si iam lo vuelve a aprobar. Cada uno publica `servicio.publicado` (activo=false).

    Si catalog aún no conoce al prestador (su `prestador.aprobado` llegará después por un
    reintento), se guarda un perfil mínimo ya suspendido con el momento del evento: así esa
    aprobación vieja se ignora y no queda activo un prestador que iam suspendió. Una
    aprobación más nueva sí lo activa.
    """

    def __init__(
        self, unidad_de_trabajo: FabricaUnidadDeTrabajo, invalidador: InvalidadorCache, reloj: Reloj
    ) -> None:
        self._uow = unidad_de_trabajo
        self._invalidador = invalidador
        self._reloj = reloj

    async def execute(self, evento: PrestadorSuspendidoRecibido) -> ResultadoConsumo:
        ahora = self._reloj.ahora()
        apagados = 0
        async with self._uow() as uow:
            if not await uow.eventos_procesados.registrar(evento.event_id, CONSUMIDOR):
                return ResultadoConsumo.DUPLICADO
            perfil = await uow.prestadores.obtener(evento.prestador_id)
            if perfil is None:
                logger.info(
                    "prestador.suspendido antes de su aprobación para %s: perfil suspendido",
                    evento.prestador_id,
                )
                perfil = PrestadorPerfil.aprobar(evento.prestador_id, evento.usuario_id, None)
                perfil.suspender()
            elif perfil.es_evento_iam_viejo(evento.ocurrido_en):
                logger.info("prestador.suspendido viejo para %s: se ignora", evento.prestador_id)
                await uow.confirmar()
                return ResultadoConsumo.IGNORADO
            elif perfil.suspender():
                for servicio in await uow.servicios.listar_por_prestador(perfil.id):
                    if servicio.desactivar_por_suspension(ahora):
                        await uow.servicios.guardar(servicio)
                        await uow.outbox.agregar(ServicioPublicado.de(servicio, ahora))
                        apagados += 1
            perfil.registrar_evento_iam(evento.ocurrido_en)
            await uow.prestadores.guardar(perfil)
            await uow.confirmar()
        if apagados:
            await self._invalidador.invalidar()
        return ResultadoConsumo.APLICADO
