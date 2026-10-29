from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4

# La sesión solo recuerda la conversación reciente (Guía Técnica §3).
MAX_MENSAJES = 10


class Rol(StrEnum):
    TURISTA = "turista"
    ASISTENTE = "asistente"


@dataclass(frozen=True)
class Mensaje:
    rol: Rol
    texto: str


@dataclass
class Conversacion:
    """Sesión del chatbot. Pertenece a un solo turista y guarda sus últimos 10 mensajes."""

    id: UUID
    turista_id: UUID
    mensajes: list[Mensaje] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._recortar()

    @classmethod
    def nueva(cls, turista_id: UUID) -> "Conversacion":
        return cls(id=uuid4(), turista_id=turista_id)

    def pertenece_a(self, turista_id: UUID) -> bool:
        return self.turista_id == turista_id

    def agregar(self, mensaje: Mensaje) -> None:
        self.mensajes.append(mensaje)
        self._recortar()

    def _recortar(self) -> None:
        del self.mensajes[:-MAX_MENSAJES]
