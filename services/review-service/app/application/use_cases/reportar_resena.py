from uuid import UUID

from app.domain.entities.reporte_resena import ROLES_QUE_REPORTAN, ReporteResena
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj
from app.domain.ports.unidad_de_trabajo import FabricaUnidadDeTrabajo
from app.domain.services.limite_reportes import VENTANA, LimiteReportes
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.motivo_reporte import MotivoReporte


class ReportarResena:
    """UC39: un turista o prestador reporta una reseña publicada que no es suya.

    El reporte no la oculta: entra en la cola del Administrador. Pasa a `EN_REVISION` al
    tercer reporte sin resolver o con el del prestador dueño, y su nota sigue contando, así
    que no publica eventos. Un reporte por usuario y reseña; como máximo 10 por hora.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._uow = unidad_de_trabajo
        self._reloj = reloj
        self._limite = LimiteReportes()

    async def execute(
        self, identidad: Identidad, resena_id: UUID, motivo: MotivoReporte, detalle: str | None
    ) -> None:
        identidad.exigir_rol(*ROLES_QUE_REPORTAN)
        ahora = self._reloj.ahora()
        async with self._uow() as uow:
            # El límite va primero: quien abusa recibe 429 aunque mande ids inventados, y no
            # puede usar la ruta para averiguar qué reseñas existen.
            recientes = await uow.reportes.recientes_de_usuario(
                identidad.usuario_id, ahora - VENTANA
            )
            self._limite.exigir(recientes, ahora)
            resena = await uow.resenas.obtener(resena_id)
            if resena is None:
                raise NoEncontrado(resena=str(resena_id))
            es_dueno = False
            if identidad.rol is Rol.PRESTADOR:
                dueno = await uow.servicios.obtener(resena.servicio_id)
                es_dueno = dueno is not None and dueno.es_dueno(identidad.usuario_id)
            reporte = ReporteResena.crear(
                resena.id, identidad.usuario_id, identidad.rol, motivo, detalle, es_dueno, ahora
            )
            resena.recibir_reporte(reporte)
            await uow.reportes.agregar(reporte)  # un duplicado da YaReportada
            await uow.resenas.guardar(resena)
            await uow.confirmar()
