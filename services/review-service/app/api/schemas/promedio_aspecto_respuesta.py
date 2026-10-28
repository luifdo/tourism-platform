from pydantic import BaseModel


class PromedioAspectoRespuesta(BaseModel):
    promedio: float
    total: int
