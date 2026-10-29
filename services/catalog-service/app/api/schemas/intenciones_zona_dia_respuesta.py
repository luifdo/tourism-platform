from datetime import date

from pydantic import BaseModel

from app.application.dto.intenciones_zona_dia import IntencionesZonaDia


class IntencionesZonaDiaRespuesta(BaseModel):
    zona: str
    fecha: date
    intenciones: int

    @classmethod
    def desde(cls, fila: IntencionesZonaDia) -> "IntencionesZonaDiaRespuesta":
        return cls(zona=fila.zona, fecha=fila.fecha, intenciones=fila.intenciones)
