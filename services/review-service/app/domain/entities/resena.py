from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4

from app.domain.entities.elegibilidad_resena import ElegibilidadResena
from app.domain.entities.reporte_resena import ReporteResena
from app.domain.entities.servicio_dueno import ServicioDueno
from app.domain.entities.versionado import Versionado
from app.domain.errors import (
    DatoInvalido,
    NoElegible,
    NoEncontrado,
    NoEsDueno,
    ResenaEnModeracion,
    ResenaPropia,
)
from app.domain.events.evento_dominio import EventoDominio
from app.domain.events.resena_ocultada import ResenaOcultada
from app.domain.events.resena_publicada import ResenaPublicada
from app.domain.value_objects.comun import texto_limpio
from app.domain.value_objects.contenido_resena import ContenidoResena
from app.domain.value_objects.decision_moderacion import DecisionModeracion
from app.domain.value_objects.estado_resena import EstadoResena
from app.domain.value_objects.respuesta_prestador import RespuestaPrestador

# Con este número de reportes sin resolver la reseña pasa a revisión.
REPORTES_PARA_REVISION = 3
MOTIVO_MAXIMO = 500


@dataclass(kw_only=True)
class Resena(Versionado):
    """Reseña de un turista sobre un servicio (UC15); una por turista y servicio.

    Se publica al instante (moderación posterior). Los reportes no la ocultan: pasa a
    `EN_REVISION` al tercer reporte sin resolver o con el reporte del prestador dueño, y aun
    así su puntuación sigue contando; solo `OCULTA` la quita del promedio. Cada cambio sube la
    versión (`If-Match`): turista, prestador y Administrador pueden tocarla a la vez.
    """

    id: UUID
    servicio_id: UUID
    turista_id: UUID
    contenido: ContenidoResena
    ultima_visita: date
    creada_en: datetime
    estado: EstadoResena = EstadoResena.PUBLICADA
    respuesta: RespuestaPrestador | None = None
    reportes_pendientes: int = 0
    editada_en: datetime | None = None

    @classmethod
    def escribir(
        cls,
        turista_id: UUID,
        servicio_id: UUID,
        elegibilidad: ElegibilidadResena | None,
        contenido: ContenidoResena,
        ahora: datetime,
    ) -> tuple["Resena", ResenaPublicada]:
        if elegibilidad is None:
            raise NoElegible(servicio=str(servicio_id))
        resena = cls(
            id=uuid4(),
            servicio_id=servicio_id,
            turista_id=turista_id,
            contenido=contenido,
            ultima_visita=elegibilidad.ultima_visita,
            creada_en=ahora,
        )
        return resena, resena._publicada(ahora)

    @property
    def mes_visita(self) -> str:
        return self.ultima_visita.strftime("%Y-%m")

    def editar(
        self,
        autor_id: UUID,
        version_esperada: int,
        contenido: ContenidoResena,
        elegibilidad: ElegibilidadResena | None,
        ahora: datetime,
    ) -> ResenaPublicada:
        """Solo su autor y mientras esté publicada; la respuesta del prestador se conserva."""
        if autor_id != self.turista_id:
            raise NoEsDueno(resena=str(self.id))
        if self.estado is not EstadoResena.PUBLICADA:
            raise ResenaEnModeracion(estado=self.estado.value)
        self._verificar_version(version_esperada)
        self.contenido = contenido
        if elegibilidad is not None:
            self.ultima_visita = max(self.ultima_visita, elegibilidad.ultima_visita)
        self.editada_en = ahora
        self._avanzar_version()
        return self._publicada(ahora)

    def responder(
        self,
        prestador_usuario_id: UUID,
        dueno: ServicioDueno | None,
        version_esperada: int,
        texto: str,
        ahora: datetime,
    ) -> None:
        """Crea o reemplaza la respuesta del dueño (UC21). En revisión sí se responde: es
        la forma de que el prestador dé su versión; oculta, no."""
        if dueno is None or not dueno.es_dueno(prestador_usuario_id):
            raise NoEsDueno(servicio=str(self.servicio_id))
        if self.estado is EstadoResena.OCULTA:
            raise ResenaEnModeracion(estado=self.estado.value)
        self._verificar_version(version_esperada)
        self.respuesta = RespuestaPrestador.escribir(texto, ahora)
        self._avanzar_version()

    def recibir_reporte(self, reporte: ReporteResena) -> bool:
        """Cuenta el reporte (UC39). Devuelve True si con él la reseña pasó a revisión.

        Solo el cambio de estado sube la versión: un reporte no debe hacer fallar por
        `If-Match` la edición del autor o la respuesta del prestador.
        """
        if reporte.usuario_id == self.turista_id:
            raise ResenaPropia(resena=str(self.id))
        if self.estado is not EstadoResena.PUBLICADA:
            raise NoEncontrado(resena=str(self.id))
        self.reportes_pendientes += 1
        if reporte.es_dueno or self.reportes_pendientes >= REPORTES_PARA_REVISION:
            self.estado = EstadoResena.EN_REVISION
            self._avanzar_version()
            return True
        return False

    def moderar(
        self,
        admin_id: UUID,
        version_esperada: int,
        decision: DecisionModeracion,
        motivo: str | None,
        ahora: datetime,
    ) -> EventoDominio | None:
        """Decisión del Administrador (UC29); cierra los reportes pendientes.

        Devuelve el evento que cambia el promedio: `resena.publicada` al sacarla de `OCULTA`
        y `resena.ocultada` al ocultarla. Ocultar una ya oculta no cambia nada.
        """
        self._verificar_version(version_esperada)
        motivo = texto_limpio(motivo, "motivo", MOTIVO_MAXIMO)
        if decision is DecisionModeracion.OCULTAR and motivo is None:
            raise DatoInvalido(campo="motivo", regla="obligatorio")
        anterior = self.estado
        destino = (
            EstadoResena.PUBLICADA
            if decision is DecisionModeracion.PUBLICAR
            else EstadoResena.OCULTA
        )
        if anterior is destino is EstadoResena.OCULTA:
            return None
        self.estado = destino
        self.reportes_pendientes = 0
        self._avanzar_version()
        if destino is EstadoResena.OCULTA:
            assert motivo is not None
            return ResenaOcultada(
                resena_id=self.id,
                servicio_id=self.servicio_id,
                turista_id=self.turista_id,
                puntuacion=self.contenido.puntuacion,
                moderada_por=admin_id,
                motivo=motivo,
                ocurrido_en=ahora,
            )
        # De EN_REVISION a PUBLICADA nunca dejó de contar: no hay evento.
        return self._publicada(ahora) if anterior is EstadoResena.OCULTA else None

    def _publicada(self, ahora: datetime) -> ResenaPublicada:
        return ResenaPublicada(
            resena_id=self.id,
            servicio_id=self.servicio_id,
            turista_id=self.turista_id,
            puntuacion=self.contenido.puntuacion,
            ocurrido_en=ahora,
        )
