"""Datos de prueba del dominio compartidos por los archivos de esta carpeta."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from app.domain.entities.elegibilidad_resena import ElegibilidadResena
from app.domain.entities.reporte_resena import ReporteResena
from app.domain.entities.resena import Resena
from app.domain.entities.servicio_dueno import ServicioDueno
from app.domain.value_objects.contenido_resena import ContenidoResena
from app.domain.value_objects.identidad import Rol
from app.domain.value_objects.motivo_reporte import MotivoReporte

AHORA = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
TURISTA = uuid4()
SERVICIO = uuid4()
DUENO = uuid4()
ADMIN = uuid4()


def elegibilidad(visita: date = date(2026, 11, 14)) -> ElegibilidadResena:
    return ElegibilidadResena(turista_id=TURISTA, servicio_id=SERVICIO, ultima_visita=visita)


def resena(puntuacion: int = 4) -> Resena:
    nueva, _ = Resena.escribir(
        TURISTA, SERVICIO, elegibilidad(), ContenidoResena(puntuacion), AHORA
    )
    return nueva


def dueno() -> ServicioDueno:
    return ServicioDueno(servicio_id=SERVICIO, prestador_usuario_id=DUENO, version=1)


def reporte(
    r: Resena, usuario: UUID | None = None, rol: Rol = Rol.TURISTA, es_dueno: bool = False
) -> ReporteResena:
    return ReporteResena.crear(
        r.id, usuario or uuid4(), rol, MotivoReporte.SPAM, None, es_dueno, AHORA
    )
