from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.domain.errors import DatoInvalido


@dataclass(kw_only=True)
class DisponibilidadDia:
    """Cupos de un servicio en un día, según booking (proyección de `disponibilidad.actualizada`).

    Sirve para buscar, no para garantizar el cupo: al reservar, booking vuelve a comprobar
    con bloqueo. `version` es la de la fila en booking: una versión menor o igual a la
    guardada se ignora, así el orden de llegada no importa.
    """

    servicio_id: UUID
    fecha: date
    cupos_totales: int
    cupos_disponibles: int
    version: int

    def __post_init__(self) -> None:
        _validar(self.cupos_totales, self.cupos_disponibles)

    def aplicar(self, cupos_totales: int, cupos_disponibles: int, version: int) -> bool:
        """Devuelve False si la versión no es más nueva que la guardada (se ignora)."""
        if version <= self.version:
            return False
        _validar(cupos_totales, cupos_disponibles)
        self.cupos_totales = cupos_totales
        self.cupos_disponibles = cupos_disponibles
        self.version = version
        return True

    def alcanza_para(self, personas: int) -> bool:
        return self.cupos_disponibles >= personas


def _validar(cupos_totales: int, cupos_disponibles: int) -> None:
    if cupos_totales < 0 or cupos_disponibles < 0:
        raise DatoInvalido(campo="cupos", regla="minimo", minimo=0)
    if cupos_disponibles > cupos_totales:
        raise DatoInvalido(campo="cupos_disponibles", regla="mayor_que", otro="cupos_totales")
