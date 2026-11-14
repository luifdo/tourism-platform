from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.errors import DatoInvalido
from app.domain.value_objects.comun import texto_limpio
from app.domain.value_objects.identidad import Rol
from app.domain.value_objects.motivo_reporte import MotivoReporte

DETALLE_MAXIMO = 500
ROLES_QUE_REPORTAN = (Rol.TURISTA, Rol.PRESTADOR)


@dataclass(kw_only=True)
class ReporteResena:
    """Reporte de una reseña inapropiada (UC39). Un usuario reporta una reseña una sola vez.

    Queda abierto hasta que el Administrador decide sobre la reseña (UC29).
    """

    id: UUID
    resena_id: UUID
    usuario_id: UUID
    rol: Rol
    motivo: MotivoReporte
    detalle: str | None
    es_dueno: bool
    reportado_en: datetime
    resuelto_en: datetime | None = None

    @classmethod
    def crear(
        cls,
        resena_id: UUID,
        usuario_id: UUID,
        rol: Rol,
        motivo: MotivoReporte,
        detalle: str | None,
        es_dueno: bool,
        ahora: datetime,
    ) -> "ReporteResena":
        detalle = texto_limpio(detalle, "detalle", DETALLE_MAXIMO)
        if motivo is MotivoReporte.OTRO and detalle is None:
            raise DatoInvalido(campo="motivo", regla="requiere", requiere="detalle")
        return cls(
            id=uuid4(),
            resena_id=resena_id,
            usuario_id=usuario_id,
            rol=rol,
            motivo=motivo,
            detalle=detalle,
            es_dueno=es_dueno,
            reportado_en=ahora,
        )

    @property
    def abierto(self) -> bool:
        return self.resuelto_en is None

    def resolver(self, ahora: datetime) -> None:
        if self.abierto:
            self.resuelto_en = ahora
