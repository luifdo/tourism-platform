"""Dobles de prueba de los puertos. Viven solo en tests/: el servicio no trae proveedor falso."""

import asyncio
import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.application.instrucciones import RESPONDER
from src.application.ports.herramientas import (
    ContextoTurista,
    DeclaracionHerramienta,
    ResultadoHerramienta,
)
from src.application.ports.modelo_de_lenguaje import (
    LlamadaHerramienta,
    MensajeModelo,
    ModeloNoDisponibleError,
    RespuestaModelo,
)
from src.domain.conversacion import Conversacion
from src.domain.recomendacion import RegistroRecomendacion

_ids = itertools.count(1)


def pedir(*llamadas: tuple[str, dict[str, Any]], texto: str = "") -> RespuestaModelo:
    """El modelo pide una o varias tools."""
    return RespuestaModelo(
        texto=texto,
        llamadas=tuple(LlamadaHerramienta(f"llamada-{next(_ids)}", n, a) for n, a in llamadas),
    )


def responder(texto: str, *recomendaciones: dict[str, Any]) -> RespuestaModelo:
    """El modelo termina con `responder_al_turista`."""
    return pedir((RESPONDER, {"respuesta": texto, "recomendaciones": list(recomendaciones)}))


def recomendacion(servicio_id: UUID | str, nombre: str, justificacion: str) -> dict[str, Any]:
    return {"servicio_id": str(servicio_id), "nombre": nombre, "justificacion": justificacion}


Paso = RespuestaModelo | Exception | Callable[[Sequence[MensajeModelo]], RespuestaModelo]


@dataclass
class Invocacion:
    instrucciones: str
    mensajes: list[MensajeModelo]
    herramientas: list[DeclaracionHerramienta]


class ModeloGuionado:
    """Responde, en orden, lo que dice su guion. Un paso puede ser una excepción."""

    nombre = "pruebas/guion"

    def __init__(self, *guion: Paso, demora_segundos: float = 0) -> None:
        self._guion = list(guion)
        self._demora_segundos = demora_segundos
        self.invocaciones: list[Invocacion] = []

    async def generar(
        self,
        instrucciones: str,
        mensajes: Sequence[MensajeModelo],
        herramientas: Sequence[DeclaracionHerramienta],
    ) -> RespuestaModelo:
        self.invocaciones.append(Invocacion(instrucciones, list(mensajes), list(herramientas)))
        if self._demora_segundos:
            await asyncio.sleep(self._demora_segundos)
        if not self._guion:
            raise AssertionError("El modelo con guion se quedó sin respuestas")
        paso = self._guion.pop(0)
        if isinstance(paso, Exception):
            raise paso
        if callable(paso):
            return paso(mensajes)
        return paso


class ModeloCaido(ModeloGuionado):
    def __init__(self) -> None:
        super().__init__(ModeloNoDisponibleError("límite de solicitudes"))


class HerramientasFalsas:
    """Tres tools que responden con datos fijos y guardan lo que se les pidió."""

    def __init__(self, servicios: Mapping[str, UUID] | None = None) -> None:
        self.ejecutadas: list[tuple[str, dict[str, Any], ContextoTurista]] = []
        self._servicios = dict(servicios or {})

    def declaraciones(self) -> Sequence[DeclaracionHerramienta]:
        return [
            DeclaracionHerramienta(n, f"tool {n}", {"type": "object", "properties": {}})
            for n in ("buscar_servicios", "alertas_oficiales", "presion_capacidad_carga")
        ]

    async def ejecutar(
        self, nombre: str, argumentos: Mapping[str, Any], contexto: ContextoTurista
    ) -> ResultadoHerramienta:
        self.ejecutadas.append((nombre, dict(argumentos), contexto))
        if nombre not in {d.nombre for d in self.declaraciones()}:
            return ResultadoHerramienta(
                nombre, {"mensaje": f"No existe la tool `{nombre}`."}, "HERRAMIENTA_DESCONOCIDA"
            )
        servicios = [{"id": str(i), "nombre": n} for n, i in self._servicios.items()]
        return ResultadoHerramienta(
            nombre, {"servicios": servicios}, servicios_vistos=frozenset(self._servicios.values())
        )


class SesionesEnMemoria:
    def __init__(self) -> None:
        self.guardadas: dict[UUID, Conversacion] = {}

    async def obtener(self, conversacion_id: UUID) -> Conversacion | None:
        return self.guardadas.get(conversacion_id)

    async def guardar(self, conversacion: Conversacion) -> None:
        self.guardadas[conversacion.id] = Conversacion(
            conversacion.id,
            conversacion.turista_id,
            list(conversacion.mensajes),
            set(conversacion.servicios_vistos),
        )


class RegistroEnMemoria:
    def __init__(self) -> None:
        self.registros: list[RegistroRecomendacion] = []

    async def registrar(self, registros: Sequence[RegistroRecomendacion]) -> None:
        self.registros.extend(registros)


class LimiteEnMemoria:
    def __init__(self, maximo: int = 1000) -> None:
        self._maximo = maximo
        self.cuentas: dict[UUID, int] = {}

    async def permitir(self, turista_id: UUID) -> bool:
        self.cuentas[turista_id] = self.cuentas.get(turista_id, 0) + 1
        return self.cuentas[turista_id] <= self._maximo
