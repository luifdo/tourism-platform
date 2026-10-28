from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.motivo_reporte import MotivoReporte


class ReporteCrear(BaseModel):
    """Cuerpo de `POST /resenas/{id}/reportes` (contrato `ReporteCrear`).

    `detalle` es obligatorio con `OTRO`; esa regla la revisa el dominio.
    """

    model_config = ConfigDict(extra="forbid")

    motivo: MotivoReporte
    detalle: str | None = Field(default=None, max_length=500)
