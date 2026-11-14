import logging

from app.application.dto.prestador_aprobado_recibido import PrestadorAprobadoRecibido
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.ports.invalidador_cache import InvalidadorCache
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.events.servicio_publicado import ServicioPublicado
from app.domain.ports.reloj import Reloj

logger = logging.getLogger(__name__)

CONSUMIDOR = "catalog.prestadores"


class AplicarPrestadorAprobado:
    """`prestador.aprobado` (UC28): crea el perfil y habilita UC17, o lo reactiva.

    Al reactivar a un suspendido vuelven solo los servicios que se apagaron por la
    suspensión; los que apagó el propio prestador siguen apagados. Cada servicio que vuelve
    publica `servicio.publicado` para booking.
    """

    def __init__(
        self, unidad_de_trabajo: FabricaUnidadDeTrabajo, invalidador: InvalidadorCache, reloj: Reloj
    ) -> None:
        self._uow = unidad_de_trabajo
        self._invalidador = invalidador
        self._reloj = reloj

    async def execute(self, evento: PrestadorAprobadoRecibido) -> ResultadoConsumo:
        ahora = self._reloj.ahora()
        restaurados = 0
        async with self._uow() as uow:
            if not await uow.eventos_procesados.registrar(evento.event_id, CONSUMIDOR):
                return ResultadoConsumo.DUPLICADO
            # Siempre perfil y luego servicios: el mismo orden de bloqueo en toda escritura.
            perfil = await uow.prestadores.obtener(evento.prestador_id)
            if perfil is None:
                perfil = PrestadorPerfil.aprobar(
                    evento.prestador_id, evento.usuario_id, evento.razon_social
                )
            elif perfil.es_evento_iam_viejo(evento.ocurrido_en):
                logger.info("prestador.aprobado viejo para %s: se ignora", evento.prestador_id)
                await uow.confirmar()  # queda registrado como procesado
                return ResultadoConsumo.IGNORADO
            elif perfil.reaprobar(evento.razon_social):
                for servicio in await uow.servicios.listar_por_prestador(perfil.id):
                    if servicio.restaurar_tras_suspension(ahora):
                        await uow.servicios.guardar(servicio)
                        await uow.outbox.agregar(ServicioPublicado.de(servicio, ahora))
                        restaurados += 1
            perfil.registrar_evento_iam(evento.ocurrido_en)
            await uow.prestadores.guardar(perfil)
            await uow.confirmar()
        if restaurados:
            await self._invalidador.invalidar()
        return ResultadoConsumo.APLICADO
