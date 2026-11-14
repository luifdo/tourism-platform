from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar


@dataclass(frozen=True, kw_only=True)
class EventoDominio:
    """Hecho del dominio que otros servicios deben conocer (contracts/events/).

    Solo define el tipo y el contenido; el sobre común (event_id, producer, correlation_id)
    lo arma el adaptador del outbox.
    """

    tipo: ClassVar[str]
    version_esquema: ClassVar[int] = 1
    ocurrido_en: datetime

    def payload(self) -> dict[str, Any]:
        raise NotImplementedError
