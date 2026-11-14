from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ResultadoLote:
    """Qué pasó con un lote del outbox. `fallo` indica que el broker no confirmó un evento."""

    publicados: tuple[str, ...] = field(default_factory=tuple)  # event_type de cada uno
    fallo: bool = False
