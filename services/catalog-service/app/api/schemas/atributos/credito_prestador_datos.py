from pydantic import BaseModel, ConfigDict

from app.api.schemas.atributos import comun
from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.value_objects.atributos.credito_prestador import CreditoPrestador


class CreditoPrestadorDatos(BaseModel):
    """El prestador cubre el gasto y el turista le paga después (acuerdo entre ellos)."""

    model_config = ConfigDict(extra="forbid")

    ofrece: bool = False
    plazo_dias: int | None = None
    condiciones: TextoTraducidoDatos | None = None

    def a_dominio(self) -> CreditoPrestador:
        return CreditoPrestador(self.ofrece, self.plazo_dias, comun.texto(self.condiciones))

    @classmethod
    def desde(cls, credito: CreditoPrestador) -> "CreditoPrestadorDatos":
        return cls(
            ofrece=credito.ofrece,
            plazo_dias=credito.plazo_dias,
            condiciones=comun.texto_datos(credito.condiciones),
        )
