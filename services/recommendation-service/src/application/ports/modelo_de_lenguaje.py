from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.application.ports.herramientas import DeclaracionHerramienta


@dataclass(frozen=True)
class LlamadaHerramienta:
    """El modelo pide ejecutar una tool. `id` enlaza la llamada con su resultado."""

    id: str
    nombre: str
    argumentos: dict[str, Any]


@dataclass(frozen=True)
class MensajeTurista:
    texto: str


@dataclass(frozen=True)
class MensajeAsistente:
    texto: str
    llamadas: tuple[LlamadaHerramienta, ...] = ()


@dataclass(frozen=True)
class ResultadoLlamada:
    llamada_id: str
    nombre: str
    contenido: dict[str, Any]


MensajeModelo = MensajeTurista | MensajeAsistente | ResultadoLlamada


@dataclass(frozen=True)
class RespuestaModelo:
    """O pide tools (`llamadas`), o responde con texto, o las dos cosas."""

    texto: str = ""
    llamadas: tuple[LlamadaHerramienta, ...] = field(default_factory=tuple)


class ModeloNoDisponibleError(Exception):
    """El proveedor no respondió, superó su límite o no hay ninguno configurado."""


class ModeloDeLenguaje(Protocol):
    """Interfaz con el proveedor de IA. Cada proveedor es un adaptador en `infrastructure/llm/`."""

    @property
    def nombre(self) -> str:
        """Proveedor y modelo, para `recomendacion_log.modelo` (p. ej. `groq/<modelo>`)."""
        ...

    async def generar(
        self,
        instrucciones: str,
        mensajes: Sequence[MensajeModelo],
        herramientas: Sequence[DeclaracionHerramienta],
    ) -> RespuestaModelo:
        """Lanza ModeloNoDisponibleError si el proveedor falla."""
        ...
