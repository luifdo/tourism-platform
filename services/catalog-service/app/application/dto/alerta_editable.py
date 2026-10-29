from dataclasses import dataclass
from datetime import datetime

from app.application.dto.estado_alerta import EstadoAlerta
from app.domain.entities.alerta_oficial import AlertaOficial


@dataclass(frozen=True, slots=True)
class AlertaEditable:
    """Alerta como la administra la Entidad: con ambos idiomas, su zona por código y su estado."""

    alerta: AlertaOficial
    zona_codigo: str | None

    def estado(self, ahora: datetime) -> EstadoAlerta:
        if not self.alerta.activa:
            return EstadoAlerta.RETIRADA
        if self.alerta.fecha_expiracion <= ahora:
            return EstadoAlerta.VENCIDA
        return EstadoAlerta.VIGENTE
