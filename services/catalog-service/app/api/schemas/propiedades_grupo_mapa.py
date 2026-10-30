from typing import Literal

from pydantic import BaseModel

from app.application.dto.grupo_en_mapa import GrupoEnMapa


class PropiedadesGrupoMapa(BaseModel):
    tipo: Literal["grupo"] = "grupo"
    conteo: int

    @classmethod
    def desde(cls, grupo: GrupoEnMapa) -> "PropiedadesGrupoMapa":
        return cls(conteo=grupo.conteo)
