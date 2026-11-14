from pydantic import BaseModel, ConfigDict

from app.api.schemas.atributos import comun
from app.api.schemas.atributos.comun import Pesos
from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.value_objects.atributos.bloque_alquiler import BloqueAlquiler


class BloqueAlquilerDatos(BaseModel):
    """Bloque F."""

    model_config = ConfigDict(extra="forbid")

    equipos: TextoTraducidoDatos
    deposito: Pesos | None = None
    requiere_documento: bool = False

    def a_dominio(self) -> BloqueAlquiler:
        return BloqueAlquiler(
            equipos=self.equipos.a_dominio(),
            deposito=comun.tarifa(self.deposito),
            requiere_documento=self.requiere_documento,
        )

    @classmethod
    def desde(cls, bloque: BloqueAlquiler) -> "BloqueAlquilerDatos":
        return cls(
            equipos=TextoTraducidoDatos.desde(bloque.equipos),
            deposito=comun.pesos(bloque.deposito),
            requiere_documento=bloque.requiere_documento,
        )
