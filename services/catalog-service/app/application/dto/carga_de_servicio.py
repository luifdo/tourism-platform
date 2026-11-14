from dataclasses import dataclass
from uuid import UUID

from app.domain.services.calculadora_saturacion import CargaServicio
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class CargaDeServicio:
    servicio_id: UUID
    nombre: TextoTraducido
    carga: CargaServicio
