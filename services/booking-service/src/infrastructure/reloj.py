from datetime import datetime, timedelta

from domain.reglas import ZONA


class RelojSistema:
    """Hora real. Admite un desfase para la demo (simular que pasaron 48 h sin esperar)."""

    def __init__(self) -> None:
        self.desfase = timedelta()

    def ahora(self) -> datetime:
        return datetime.now(ZONA) + self.desfase

    def avanzar(self, **delta: float) -> None:
        self.desfase += timedelta(**delta)


class RelojFijo:
    """Para pruebas: la hora solo cambia cuando se avanza a mano."""

    def __init__(self, ahora: datetime):
        self._ahora = ahora

    def ahora(self) -> datetime:
        return self._ahora

    def avanzar(self, **delta: float) -> None:
        self._ahora += timedelta(**delta)
