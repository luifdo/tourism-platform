from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(kw_only=True)
class ElegibilidadResena:
    """El turista tiene al menos una reserva finalizada del servicio (`reserva.finalizada`).

    Guarda la visita más reciente: da el mes que se muestra en la reseña.
    """

    turista_id: UUID
    servicio_id: UUID
    ultima_visita: date

    def registrar_visita(self, fecha: date) -> bool:
        """Se queda con la fecha más reciente, así que el orden y los duplicados no importan.
        Devuelve True si cambió."""
        if fecha <= self.ultima_visita:
            return False
        self.ultima_visita = fecha
        return True
