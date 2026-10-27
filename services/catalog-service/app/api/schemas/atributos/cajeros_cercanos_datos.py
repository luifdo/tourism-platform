from pydantic import BaseModel, ConfigDict

from app.api.schemas.atributos import comun
from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.value_objects.atributos.cajeros_cercanos import CajerosCercanos


class CajerosCercanosDatos(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hay_cerca: bool
    referencia: TextoTraducidoDatos | None = None
    distancia_km: float | None = None

    def a_dominio(self) -> CajerosCercanos:
        return CajerosCercanos(self.hay_cerca, comun.texto(self.referencia), self.distancia_km)

    @classmethod
    def desde(cls, cajeros: CajerosCercanos) -> "CajerosCercanosDatos":
        return cls(
            hay_cerca=cajeros.hay_cerca,
            referencia=comun.texto_datos(cajeros.referencia),
            distancia_km=cajeros.distancia_km,
        )
