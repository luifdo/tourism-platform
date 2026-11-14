from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class DeclaracionHerramienta:
    """Lo que el modelo ve de una tool, en un formato propio (no el de un proveedor).

    `parametros` es un JSON Schema de tipo objeto; cada adaptador de `llm/` lo traduce al
    formato de su proveedor.
    """

    nombre: str
    descripcion: str
    parametros: dict[str, Any]


@dataclass(frozen=True)
class ContextoTurista:
    """Lo que el servidor sabe de quién pregunta. El modelo nunca lo decide."""

    turista_id: UUID
    idioma: Literal["es", "en"] = "es"


@dataclass(frozen=True)
class ResultadoHerramienta:
    """Resultado de ejecutar una tool, listo para devolvérselo al modelo.

    `datos` es lo mínimo que el modelo necesita. Si la tool falló, `error` trae el código
    y `datos` el motivo, para que el modelo diga que no pudo consultar en lugar de inventar.
    `servicios_vistos` son los servicios que aparecieron en el resultado: el chatbot solo
    puede recomendar esos (Guía Técnica §6).
    """

    nombre: str
    datos: dict[str, Any]
    error: str | None = None
    servicios_vistos: frozenset[UUID] = field(default_factory=frozenset)

    @property
    def ok(self) -> bool:
        return self.error is None


class Herramientas(Protocol):
    """Las tools de solo lectura que el chatbot puede pedir (Guía Técnica §5)."""

    def declaraciones(self) -> Sequence[DeclaracionHerramienta]: ...

    async def ejecutar(
        self, nombre: str, argumentos: Mapping[str, Any], contexto: ContextoTurista
    ) -> ResultadoHerramienta:
        """Nunca lanza excepciones por fallas de la tool: las devuelve como resultado."""
        ...
