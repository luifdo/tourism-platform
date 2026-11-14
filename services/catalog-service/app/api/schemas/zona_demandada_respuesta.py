from pydantic import BaseModel

from app.api.schemas.zona_resumen_respuesta import ZonaResumenRespuesta
from app.application.dto.zona_demandada import ZonaDemandada
from app.domain.value_objects.idioma import Idioma


class ZonaDemandadaRespuesta(BaseModel):
    zona: ZonaResumenRespuesta
    personas: int
    intenciones_visita: int

    @classmethod
    def desde(cls, z: ZonaDemandada, idioma: Idioma) -> "ZonaDemandadaRespuesta":
        zona = ZonaResumenRespuesta.desde(z.zona, idioma)
        assert zona is not None
        return cls(zona=zona, personas=z.personas, intenciones_visita=z.intenciones_visita)
