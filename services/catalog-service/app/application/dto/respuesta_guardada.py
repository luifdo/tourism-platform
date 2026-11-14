from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RespuestaGuardada:
    """Respuesta de una operación idempotente, para devolverla igual en cada reintento."""

    estado: int
    cuerpo: bytes
    cabeceras: dict[str, str] = field(default_factory=dict)
