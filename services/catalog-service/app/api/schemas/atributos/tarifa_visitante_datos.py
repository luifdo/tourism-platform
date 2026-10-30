from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.api.schemas.atributos.comun import Pesos
from app.domain.value_objects.atributos.tarifa_visitante import TarifaVisitante
from app.domain.value_objects.atributos.valores import TipoVisitante
from app.domain.value_objects.tarifa import Tarifa


class TarifaVisitanteDatos(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_visitante: TipoVisitante
    valor: Pesos

    def a_dominio(self) -> TarifaVisitante:
        return TarifaVisitante(self.tipo_visitante, Tarifa(Decimal(str(self.valor))))

    @classmethod
    def desde(cls, tarifa: TarifaVisitante) -> "TarifaVisitanteDatos":
        return cls(tipo_visitante=tarifa.tipo_visitante, valor=float(tarifa.valor.valor))
