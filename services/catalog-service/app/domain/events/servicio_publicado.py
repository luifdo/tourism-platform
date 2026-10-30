from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

from app.domain.entities.atractivo_servicio import AtractivoServicio
from app.domain.events.evento_dominio import EventoDominio


@dataclass(frozen=True, kw_only=True)
class ServicioPublicado(EventoDominio):
    """`servicio.publicado.v1`: estado completo que booking necesita (dueño, aforo, activo).

    Lleva la versión del servicio: booking descarta los mensajes con versión menor o igual a
    la que ya tiene, así el orden de llegada no importa.
    """

    tipo: ClassVar[str] = "servicio.publicado"
    servicio: AtractivoServicio

    @classmethod
    def de(cls, servicio: AtractivoServicio, ahora: datetime) -> "ServicioPublicado":
        return cls(servicio=servicio, ocurrido_en=ahora)

    def payload(self) -> dict[str, Any]:
        s = self.servicio
        return {
            "servicio_id": str(s.id),
            "prestador_id": str(s.prestador_id),
            "prestador_usuario_id": str(s.prestador_usuario_id),
            "capacidad_aforo_diario": s.datos.capacidad_aforo_diario,
            "tarifa_base": float(s.datos.tarifa_base.valor),
            "activo": s.activo,
            "version": s.version,
        }
