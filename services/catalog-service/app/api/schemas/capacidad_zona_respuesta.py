from datetime import date, datetime

from pydantic import BaseModel

from app.api.i18n.etiquetas import etiqueta
from app.api.schemas.servicio_con_bandera_respuesta import ServicioConBanderaRespuesta
from app.api.schemas.zona_resumen_respuesta import ZonaResumenRespuesta
from app.application.dto.capacidad_zona import CapacidadZona
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.saturacion import NivelSaturacion


class CapacidadZonaRespuesta(BaseModel):
    """Para el turista solo van zona, fecha y nivel: el detalle es para la Entidad."""

    zona: ZonaResumenRespuesta
    fecha: date
    nivel: NivelSaturacion
    nivel_etiqueta: str
    personas_activas: int | None = None
    capacidad: int | None = None
    indice: float | None = None
    calculado_en: datetime | None = None
    servicios_con_bandera: list[ServicioConBanderaRespuesta] | None = None

    @classmethod
    def desde(
        cls, capacidad: CapacidadZona, idioma: Idioma, solo_nivel: bool
    ) -> "CapacidadZonaRespuesta":
        zona = ZonaResumenRespuesta.desde(capacidad.zona, idioma)
        assert zona is not None
        s = capacidad.saturacion
        base = cls(
            zona=zona,
            fecha=capacidad.fecha,
            nivel=s.nivel,
            nivel_etiqueta=etiqueta(s.nivel, idioma),
        )
        if solo_nivel:
            return base
        return base.model_copy(
            update={
                "personas_activas": s.personas_activas,
                "capacidad": s.capacidad,
                "indice": s.indice,
                "calculado_en": capacidad.calculado_en,
                "servicios_con_bandera": [
                    ServicioConBanderaRespuesta.desde(b, idioma)
                    for b in capacidad.servicios_con_bandera
                ],
            }
        )
