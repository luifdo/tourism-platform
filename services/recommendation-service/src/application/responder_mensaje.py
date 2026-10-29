"""Caso de uso del chat (UC14, flujo 6 del Plan de Implementación)."""

import asyncio
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.application.instrucciones import (
    DECLARACION_RESPONDER,
    MENSAJE_LIMITE,
    MENSAJE_VACIO,
    RESPONDER,
    Idioma,
    instrucciones,
)
from src.application.ports.herramientas import ContextoTurista, Herramientas, ResultadoHerramienta
from src.application.ports.modelo_de_lenguaje import (
    MensajeAsistente,
    MensajeModelo,
    MensajeTurista,
    ModeloDeLenguaje,
    ModeloNoDisponibleError,
    ResultadoLlamada,
)
from src.application.ports.registro_recomendaciones import RegistroRecomendaciones
from src.application.ports.repositorio_sesiones import RepositorioSesiones
from src.domain.conversacion import Conversacion, Mensaje, Rol
from src.domain.recomendacion import Recomendacion, RegistroRecomendacion

logger = logging.getLogger(__name__)

# Guía Técnica §6: máximo 6 llamadas a tools de la plataforma por mensaje.
MAX_LLAMADAS = 6


class ConversacionNoEncontradaError(Exception):
    """No existe, expiró o es de otro turista; los tres casos se responden igual (404)."""


class AsistenteNoDisponibleError(Exception):
    """El proveedor de IA falló o la consulta superó su tiempo máximo (503)."""


@dataclass(frozen=True)
class PeticionChat:
    turista_id: UUID
    mensaje: str
    idioma: Idioma = "es"
    conversacion_id: UUID | None = None


@dataclass(frozen=True)
class ResultadoChat:
    conversacion_id: UUID
    respuesta: str
    recomendaciones: tuple[Recomendacion, ...]


@dataclass(frozen=True)
class _Turno:
    respuesta: str
    recomendaciones: tuple[Recomendacion, ...]
    herramientas_usadas: tuple[str, ...]


class ResponderMensaje:
    def __init__(
        self,
        modelo: ModeloDeLenguaje,
        herramientas: Herramientas,
        sesiones: RepositorioSesiones,
        registro: RegistroRecomendaciones,
        reloj: Callable[[], datetime],
        timeout_segundos: float = 45.0,
        max_llamadas: int = MAX_LLAMADAS,
    ) -> None:
        self._modelo = modelo
        self._herramientas = herramientas
        self._sesiones = sesiones
        self._registro = registro
        self._reloj = reloj
        self._timeout_segundos = timeout_segundos
        self._max_llamadas = max_llamadas

    async def ejecutar(self, peticion: PeticionChat) -> ResultadoChat:
        conversacion = await self._conversacion(peticion)
        try:
            async with asyncio.timeout(self._timeout_segundos):
                turno = await self._conversar(conversacion, peticion)
        except ModeloNoDisponibleError as exc:
            logger.warning("El proveedor de IA no está disponible: %s", exc)
            raise AsistenteNoDisponibleError() from exc
        except TimeoutError as exc:
            logger.warning("La consulta superó %s s", self._timeout_segundos)
            raise AsistenteNoDisponibleError() from exc

        await self._registro.registrar(
            [
                RegistroRecomendacion(
                    conversacion_id=conversacion.id,
                    turista_id=peticion.turista_id,
                    servicio_id=r.servicio_id,
                    justificacion=r.justificacion,
                    herramientas_usadas=list(turno.herramientas_usadas),
                    modelo=self._modelo.nombre,
                    fecha_generacion=self._reloj(),
                )
                for r in turno.recomendaciones
            ]
        )
        conversacion.agregar(Mensaje(rol=Rol.TURISTA, texto=peticion.mensaje))
        conversacion.agregar(Mensaje(rol=Rol.ASISTENTE, texto=turno.respuesta))
        await self._sesiones.guardar(conversacion)
        return ResultadoChat(conversacion.id, turno.respuesta, turno.recomendaciones)

    async def _conversacion(self, peticion: PeticionChat) -> Conversacion:
        if peticion.conversacion_id is None:
            return Conversacion.nueva(peticion.turista_id)
        conversacion = await self._sesiones.obtener(peticion.conversacion_id)
        if conversacion is None or not conversacion.pertenece_a(peticion.turista_id):
            raise ConversacionNoEncontradaError()
        return conversacion

    async def _conversar(self, conversacion: Conversacion, peticion: PeticionChat) -> _Turno:
        contexto = ContextoTurista(turista_id=peticion.turista_id, idioma=peticion.idioma)
        declaraciones = [*self._herramientas.declaraciones(), DECLARACION_RESPONDER]
        mensajes: list[MensajeModelo] = [_del_historial(m) for m in conversacion.mensajes]
        mensajes.append(MensajeTurista(peticion.mensaje))
        usadas: list[str] = []

        # Termina siempre: cada vuelta responde o ejecuta al menos una tool de las 6 permitidas.
        while True:
            respuesta = await self._modelo.generar(
                instrucciones(peticion.idioma), mensajes, declaraciones
            )
            final = next((ll for ll in respuesta.llamadas if ll.nombre == RESPONDER), None)
            if final is not None:
                texto, recomendaciones = _leer_final(final.argumentos, respuesta.texto)
                return _turno(texto or MENSAJE_VACIO[peticion.idioma], recomendaciones, usadas)
            if not respuesta.llamadas:
                texto = respuesta.texto.strip() or MENSAJE_VACIO[peticion.idioma]
                return _turno(texto, (), usadas)
            if len(usadas) + len(respuesta.llamadas) > self._max_llamadas:
                logger.info("Se alcanzó el límite de %s tools en un mensaje", self._max_llamadas)
                return _turno(MENSAJE_LIMITE[peticion.idioma], (), usadas)

            resultados = await asyncio.gather(
                *(
                    self._herramientas.ejecutar(ll.nombre, ll.argumentos, contexto)
                    for ll in respuesta.llamadas
                )
            )
            mensajes.append(MensajeAsistente(respuesta.texto, respuesta.llamadas))
            for llamada, resultado in zip(respuesta.llamadas, resultados, strict=True):
                usadas.append(llamada.nombre)
                mensajes.append(ResultadoLlamada(llamada.id, llamada.nombre, _contenido(resultado)))


def _del_historial(mensaje: Mensaje) -> MensajeModelo:
    if mensaje.rol is Rol.TURISTA:
        return MensajeTurista(mensaje.texto)
    return MensajeAsistente(mensaje.texto)


def _contenido(resultado: ResultadoHerramienta) -> dict[str, Any]:
    if resultado.ok:
        return resultado.datos
    return {"error": resultado.error, **resultado.datos}


def _turno(texto: str, recomendaciones: tuple[Recomendacion, ...], usadas: list[str]) -> _Turno:
    # Sin repetidos y en el orden en que se usaron.
    return _Turno(texto, recomendaciones, tuple(dict.fromkeys(usadas)))


def _leer_final(argumentos: Mapping[str, Any], texto: str) -> tuple[str, tuple[Recomendacion, ...]]:
    """Lee los argumentos de `responder_al_turista`, descartando lo que venga mal formado."""
    respuesta = argumentos.get("respuesta")
    if not isinstance(respuesta, str) or not respuesta.strip():
        respuesta = texto
    items = argumentos.get("recomendaciones")
    recomendaciones = []
    for item in items if isinstance(items, list) else []:
        try:
            recomendaciones.append(
                Recomendacion(
                    servicio_id=UUID(str(item["servicio_id"])),
                    nombre=str(item["nombre"]),
                    justificacion=str(item["justificacion"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            logger.info("Se descartó una recomendación mal formada: %r", item)
    return respuesta.strip(), tuple(recomendaciones)
