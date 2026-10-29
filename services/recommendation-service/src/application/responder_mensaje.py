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
    HORA_COLOMBIA,
    MENSAJE_LIMITE,
    MENSAJE_VACIO,
    ORIGEN_DATOS,
    RESPONDER,
    Idioma,
    instrucciones,
)
from src.application.ports.herramientas import ContextoTurista, Herramientas, ResultadoHerramienta
from src.application.ports.limite_de_tasa import LimiteDeTasa
from src.application.ports.modelo_de_lenguaje import (
    LlamadaHerramienta,
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
from src.domain.privacidad import ocultar_datos_personales
from src.domain.recomendacion import Recomendacion, RegistroRecomendacion
from src.domain.texto_plano import a_texto_plano

logger = logging.getLogger(__name__)

# Guía Técnica §6: máximo 6 llamadas a tools de la plataforma por mensaje.
MAX_LLAMADAS = 6


class ConversacionNoEncontradaError(Exception):
    """No existe, expiró o es de otro turista; los tres casos se responden igual (404)."""


class AsistenteNoDisponibleError(Exception):
    """El proveedor de IA falló o la consulta superó su tiempo máximo (503)."""


class DemasiadasSolicitudesError(Exception):
    """El turista superó el límite de mensajes de la ventana (429)."""


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
    servicios_vistos: frozenset[UUID]


class ResponderMensaje:
    def __init__(
        self,
        modelo: ModeloDeLenguaje,
        herramientas: Herramientas,
        sesiones: RepositorioSesiones,
        registro: RegistroRecomendaciones,
        limite: LimiteDeTasa,
        reloj: Callable[[], datetime],
        timeout_segundos: float = 45.0,
        max_llamadas: int = MAX_LLAMADAS,
    ) -> None:
        self._modelo = modelo
        self._herramientas = herramientas
        self._sesiones = sesiones
        self._registro = registro
        self._limite = limite
        self._reloj = reloj
        self._timeout_segundos = timeout_segundos
        self._max_llamadas = max_llamadas

    async def ejecutar(self, peticion: PeticionChat) -> ResultadoChat:
        if not await self._limite.permitir(peticion.turista_id):
            raise DemasiadasSolicitudesError()
        conversacion = await self._conversacion(peticion)
        # Lo que el turista escriba de correo o celular no se guarda ni viaja al proveedor.
        mensaje = ocultar_datos_personales(peticion.mensaje.strip())
        try:
            async with asyncio.timeout(self._timeout_segundos):
                turno = await self._conversar(conversacion, mensaje, peticion.idioma)
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
        conversacion.agregar(Mensaje(rol=Rol.TURISTA, texto=mensaje))
        conversacion.agregar(Mensaje(rol=Rol.ASISTENTE, texto=turno.respuesta))
        conversacion.servicios_vistos |= turno.servicios_vistos
        await self._sesiones.guardar(conversacion)
        return ResultadoChat(conversacion.id, turno.respuesta, turno.recomendaciones)

    async def _conversacion(self, peticion: PeticionChat) -> Conversacion:
        if peticion.conversacion_id is None:
            return Conversacion.nueva(peticion.turista_id)
        conversacion = await self._sesiones.obtener(peticion.conversacion_id)
        if conversacion is None or not conversacion.pertenece_a(peticion.turista_id):
            raise ConversacionNoEncontradaError()
        return conversacion

    async def _conversar(self, conversacion: Conversacion, mensaje: str, idioma: Idioma) -> _Turno:
        # La identidad va solo al contexto de las tools; nunca en lo que se envía al modelo.
        contexto = ContextoTurista(turista_id=conversacion.turista_id, idioma=idioma)
        de_la_plataforma = [*self._herramientas.declaraciones()]
        conocidas = {d.nombre for d in de_la_plataforma}
        declaraciones = [*de_la_plataforma, DECLARACION_RESPONDER]
        mensajes: list[MensajeModelo] = [_del_historial(m) for m in conversacion.mensajes]
        mensajes.append(MensajeTurista(mensaje))
        llamadas_hechas = 0
        # Solo tools que existen: van a `recomendacion_log.herramientas_usadas`.
        usadas: list[str] = []
        vistos = set(conversacion.servicios_vistos)
        texto_sistema = instrucciones(idioma, self._reloj().astimezone(HORA_COLOMBIA).date())

        def turno(texto: str, recomendaciones: tuple[Recomendacion, ...] = ()) -> _Turno:
            # Tools sin repetidos y en el orden en que se usaron.
            return _Turno(texto, recomendaciones, tuple(dict.fromkeys(usadas)), frozenset(vistos))

        # Termina siempre: cada vuelta responde o ejecuta al menos una tool de las 6 permitidas.
        while True:
            respuesta = await self._modelo.generar(texto_sistema, mensajes, declaraciones)
            final = next((ll for ll in respuesta.llamadas if _es_final(ll, conocidas)), None)
            if final is not None:
                texto, propuestas = _leer_final(final.argumentos, respuesta.texto)
                return turno(texto or MENSAJE_VACIO[idioma], _validar(propuestas, vistos))
            if not respuesta.llamadas:
                return turno(a_texto_plano(respuesta.texto) or MENSAJE_VACIO[idioma])
            if llamadas_hechas + len(respuesta.llamadas) > self._max_llamadas:
                logger.info("Se alcanzó el límite de %s tools en un mensaje", self._max_llamadas)
                return turno(MENSAJE_LIMITE[idioma])

            resultados = await asyncio.gather(
                *(
                    self._herramientas.ejecutar(ll.nombre, ll.argumentos, contexto)
                    for ll in respuesta.llamadas
                )
            )
            mensajes.append(MensajeAsistente(respuesta.texto, respuesta.llamadas))
            for llamada, resultado in zip(respuesta.llamadas, resultados, strict=True):
                llamadas_hechas += 1
                if llamada.nombre in conocidas:
                    usadas.append(llamada.nombre)
                vistos |= resultado.servicios_vistos
                mensajes.append(ResultadoLlamada(llamada.id, llamada.nombre, _contenido(resultado)))


def _es_final(llamada: LlamadaHerramienta, conocidas: set[str]) -> bool:
    """La tool final, o una desconocida que trae su forma: algunos modelos (gpt-oss) la
    llaman `json` u otro nombre. Tomarla como final ahorra una vuelta al proveedor."""
    if llamada.nombre == RESPONDER:
        return True
    return llamada.nombre not in conocidas and "respuesta" in llamada.argumentos


def _del_historial(mensaje: Mensaje) -> MensajeModelo:
    if mensaje.rol is Rol.TURISTA:
        return MensajeTurista(mensaje.texto)
    return MensajeAsistente(mensaje.texto)


def _contenido(resultado: ResultadoHerramienta) -> dict[str, Any]:
    """Envuelve el resultado para que el modelo lo trate como datos, no como instrucciones."""
    contenido: dict[str, Any] = {"origen": ORIGEN_DATOS, "datos": resultado.datos}
    if not resultado.ok:
        contenido["error"] = resultado.error
    return contenido


def _leer_final(argumentos: Mapping[str, Any], texto: str) -> tuple[str, list[Recomendacion]]:
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
                    justificacion=a_texto_plano(str(item["justificacion"])),
                )
            )
        except (KeyError, TypeError, ValueError):
            # Incluye la recomendación sin justificación (RNF-08).
            logger.info("Se descartó una recomendación mal formada: %r", item)
    return a_texto_plano(respuesta), recomendaciones


def _validar(propuestas: list[Recomendacion], vistos: set[UUID]) -> tuple[Recomendacion, ...]:
    """Solo pasan servicios que salieron de una tool en la conversación, sin repetir (Guía §6)."""
    validas: dict[UUID, Recomendacion] = {}
    for recomendacion in propuestas:
        if recomendacion.servicio_id not in vistos:
            logger.warning(
                "Se descartó un servicio que no salió de ninguna tool: %s",
                recomendacion.servicio_id,
            )
            continue
        validas.setdefault(recomendacion.servicio_id, recomendacion)
    return tuple(validas.values())
