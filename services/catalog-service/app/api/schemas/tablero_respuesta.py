from datetime import date

from pydantic import BaseModel

from app.api.schemas.capacidad_zona_respuesta import CapacidadZonaRespuesta
from app.api.schemas.punto_demanda_respuesta import PuntoDemandaRespuesta
from app.api.schemas.zona_demandada_respuesta import ZonaDemandadaRespuesta
from app.application.dto.tablero import Tablero
from app.domain.value_objects.idioma import Idioma


class TableroRespuesta(BaseModel):
    desde: date
    hasta: date
    totales: PuntoDemandaRespuesta
    capacidad_hoy: list[CapacidadZonaRespuesta]
    zonas_mas_demandadas: list[ZonaDemandadaRespuesta]
    alertas_vigentes: int

    @classmethod
    def desde_dto(cls, t: Tablero, idioma: Idioma) -> "TableroRespuesta":
        return cls(
            desde=t.rango.desde,
            hasta=t.rango.hasta,
            totales=PuntoDemandaRespuesta.desde(t.totales),
            capacidad_hoy=[
                CapacidadZonaRespuesta.desde(c, idioma, solo_nivel=False) for c in t.capacidad_hoy
            ],
            zonas_mas_demandadas=[
                ZonaDemandadaRespuesta.desde(z, idioma) for z in t.zonas_mas_demandadas
            ],
            alertas_vigentes=t.alertas_vigentes,
        )
