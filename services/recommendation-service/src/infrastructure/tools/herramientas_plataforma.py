import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel, ValidationError

from src.application.ports.herramientas import (
    ContextoTurista,
    DeclaracionHerramienta,
    ResultadoHerramienta,
)
from src.infrastructure.tools import argumentos, recortes

logger = logging.getLogger(__name__)

TAMANO_BUSQUEDA = 8
TAMANO_RESENAS = 5
TAMANO_HISTORIAL = 20


class _FallaHerramientaError(Exception):
    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


@dataclass(frozen=True)
class _Salida:
    datos: dict[str, Any]
    servicios_vistos: frozenset[UUID] = field(default_factory=frozenset)


@dataclass(frozen=True)
class _Definicion:
    modelo: type[BaseModel]
    descripcion: str
    ejecutar: Callable[[Any, ContextoTurista], Awaitable[_Salida]]


class HerramientasPlataforma:
    """Implementa Herramientas con llamadas HTTP de solo lectura a catalog, booking y review."""

    def __init__(
        self, cliente: httpx.AsyncClient, catalog_url: str, booking_url: str, review_url: str
    ) -> None:
        self._cliente = cliente
        self._catalog = catalog_url.rstrip("/")
        self._booking = booking_url.rstrip("/")
        self._review = review_url.rstrip("/")
        self._definiciones = {
            "buscar_servicios": _Definicion(
                argumentos.BuscarServicios,
                "Busca servicios turísticos de Santa Marta en el catálogo de la plataforma "
                "(atractivos, actividades, alojamiento, gastronomía, transporte). Úsala cuando el "
                f"turista pida opciones o ideas. Devuelve hasta {TAMANO_BUSQUEDA} servicios con "
                "su `id`; solo puedes recomendar servicios que hayan salido de una tool.",
                self._buscar_servicios,
            ),
            "detalle_servicio": _Definicion(
                argumentos.DetalleServicio,
                "Ficha de un servicio: descripción, tarifa, prestador, regla de cancelación, "
                "alertas vigentes y qué dinero conviene llevar.",
                self._detalle_servicio,
            ),
            "consultar_disponibilidad": _Definicion(
                argumentos.ConsultarDisponibilidad,
                "Cupos disponibles por día de un servicio. Úsala cuando el turista mencione una "
                "fecha o pregunte si hay cupo. Para reservar, el turista abre la ficha del "
                "servicio.",
                self._consultar_disponibilidad,
            ),
            "historial_turista": _Definicion(
                argumentos.HistorialTurista,
                "Reservas del turista que está conversando (solo las suyas). Úsala para "
                "personalizar según lo que ya reservó o visitó.",
                self._historial_turista,
            ),
            "resenas_servicio": _Definicion(
                argumentos.ResenasServicio,
                f"Calificación promedio y las {TAMANO_RESENAS} reseñas más recientes de un "
                "servicio.",
                self._resenas_servicio,
            ),
            "presion_capacidad_carga": _Definicion(
                argumentos.PresionCapacidadCarga,
                "Nivel de saturación de cada zona frente a su capacidad de carga (BAJO, MEDIO o "
                "ALTO). Úsala para preferir zonas con nivel BAJO y advertir sobre las de nivel "
                "ALTO.",
                self._presion_capacidad_carga,
            ),
            "alertas_oficiales": _Definicion(
                argumentos.AlertasOficiales,
                "Alertas oficiales vigentes (cierres, clima, saturación) por zona o por servicio. "
                "Consúltala antes de recomendar una zona.",
                self._alertas_oficiales,
            ),
        }
        self._declaraciones = [
            DeclaracionHerramienta(nombre, d.descripcion, argumentos.esquema(d.modelo))
            for nombre, d in self._definiciones.items()
        ]

    def declaraciones(self) -> Sequence[DeclaracionHerramienta]:
        return self._declaraciones

    async def ejecutar(
        self, nombre: str, argumentos_modelo: Mapping[str, Any], contexto: ContextoTurista
    ) -> ResultadoHerramienta:
        definicion = self._definiciones.get(nombre)
        if definicion is None:
            disponibles = ", ".join(self._definiciones)
            return _fallo(
                nombre,
                "HERRAMIENTA_DESCONOCIDA",
                f"No existe la tool `{nombre}`. Las disponibles son: {disponibles}.",
            )
        if not isinstance(argumentos_modelo, Mapping):
            return _fallo(nombre, "ARGUMENTOS_INVALIDOS", "Los argumentos deben ser un objeto.")
        try:
            # El modelo suele mandar null en los opcionales que no usa.
            args = definicion.modelo.model_validate(
                {k: v for k, v in argumentos_modelo.items() if v is not None}
            )
        except ValidationError as exc:
            return _fallo(nombre, "ARGUMENTOS_INVALIDOS", _explicar(exc))

        try:
            salida = await definicion.ejecutar(args, contexto)
        except _FallaHerramientaError as exc:
            return _fallo(nombre, exc.codigo, exc.mensaje)
        except httpx.ConnectTimeout:
            # Ni siquiera se pudo conectar: el servicio está caído, no lento.
            logger.warning("La tool %s no pudo conectarse a tiempo", nombre)
            return _fallo(
                nombre, "SERVICIO_NO_DISPONIBLE", "El servicio de la plataforma no responde."
            )
        except httpx.TimeoutException:
            logger.warning("La tool %s agotó el tiempo de espera", nombre)
            return _fallo(nombre, "TIEMPO_AGOTADO", "El servicio tardó demasiado en responder.")
        except httpx.HTTPError:
            logger.warning("La tool %s no pudo conectarse", nombre, exc_info=True)
            return _fallo(
                nombre, "SERVICIO_NO_DISPONIBLE", "El servicio de la plataforma no responde."
            )
        except (KeyError, TypeError, ValueError):
            # ValueError incluye el JSON mal formado (json.JSONDecodeError).
            logger.warning("La tool %s recibió una respuesta inesperada", nombre, exc_info=True)
            return _fallo(
                nombre, "RESPUESTA_INESPERADA", "El servicio respondió algo que no se entiende."
            )
        return ResultadoHerramienta(
            nombre=nombre, datos=salida.datos, servicios_vistos=salida.servicios_vistos
        )

    # ---------- tools ----------

    async def _buscar_servicios(
        self, args: argumentos.BuscarServicios, contexto: ContextoTurista
    ) -> _Salida:
        cuerpo = await self._get(
            f"{self._catalog}/buscar",
            contexto,
            params={
                "texto": args.texto,
                "categoria": ",".join(args.categorias) if args.categorias else None,
                "zona": args.zona,
                "precio_max": args.precio_max,
                "fecha": args.fecha,
                "personas": args.personas,
                "lat": args.lat,
                "lon": args.lon,
                "tamano": TAMANO_BUSQUEDA,
            },
        )
        return _Salida(recortes.busqueda(cuerpo), _ids(i["id"] for i in cuerpo["items"]))

    async def _detalle_servicio(
        self, args: argumentos.DetalleServicio, contexto: ContextoTurista
    ) -> _Salida:
        cuerpo = await self._get(f"{self._catalog}/servicios/{args.servicio_id}", contexto)
        return _Salida(recortes.detalle(cuerpo), _ids([cuerpo["id"]]))

    async def _consultar_disponibilidad(
        self, args: argumentos.ConsultarDisponibilidad, contexto: ContextoTurista
    ) -> _Salida:
        cuerpo = await self._get(
            f"{self._booking}/disponibilidad",
            contexto,
            params={
                "servicio_id": args.servicio_id,
                "desde": args.desde,
                "hasta": args.hasta or args.desde,
            },
        )
        return _Salida(recortes.disponibilidad(cuerpo))

    async def _historial_turista(
        self, _: argumentos.HistorialTurista, contexto: ContextoTurista
    ) -> _Salida:
        cuerpo = await self._get(
            f"{self._booking}/mis-reservas",
            contexto,
            params={"tamano": TAMANO_HISTORIAL},
            con_identidad=True,
        )
        return _Salida(recortes.historial(cuerpo), _ids(r["servicio_id"] for r in cuerpo["items"]))

    async def _resenas_servicio(
        self, args: argumentos.ResenasServicio, contexto: ContextoTurista
    ) -> _Salida:
        base = f"{self._review}/servicios/{args.servicio_id}"
        resumen, pagina = await asyncio.gather(
            self._get(f"{base}/resumen", contexto),
            self._get(
                f"{base}/resenas", contexto, params={"orden": "recientes", "tamano": TAMANO_RESENAS}
            ),
        )
        return _Salida(recortes.resenas(resumen, pagina))

    async def _presion_capacidad_carga(
        self, args: argumentos.PresionCapacidadCarga, contexto: ContextoTurista
    ) -> _Salida:
        cuerpo = await self._get(
            f"{self._catalog}/analitica/capacidad",
            contexto,
            params={"zona": args.zona, "fecha": args.fecha},
            con_identidad=True,
        )
        return _Salida(recortes.capacidad(cuerpo))

    async def _alertas_oficiales(
        self, args: argumentos.AlertasOficiales, contexto: ContextoTurista
    ) -> _Salida:
        cuerpo = await self._get(
            f"{self._catalog}/alertas",
            contexto,
            params={"zona": args.zona, "servicio_id": args.servicio_id},
        )
        return _Salida(recortes.alertas(cuerpo))

    # ---------- HTTP ----------

    async def _get(
        self,
        url: str,
        contexto: ContextoTurista,
        *,
        params: Mapping[str, Any] | None = None,
        con_identidad: bool = False,
    ) -> Any:
        cabeceras = {"Accept-Language": contexto.idioma}
        if con_identidad:
            # Como Traefik tras validar el JWT: el turista sale del contexto, no del modelo.
            cabeceras |= {"X-Usuario-Id": str(contexto.turista_id), "X-Usuario-Rol": "Turista"}
        respuesta = await self._cliente.get(url, params=_parametros(params), headers=cabeceras)
        if respuesta.status_code == httpx.codes.NOT_FOUND:
            raise _FallaHerramientaError("NO_ENCONTRADO", "No existe o no está disponible.")
        if respuesta.status_code == httpx.codes.BAD_REQUEST:
            raise _FallaHerramientaError("SOLICITUD_RECHAZADA", _mensaje_de_error(respuesta))
        if respuesta.status_code != httpx.codes.OK:
            logger.warning("%s respondió %s", url, respuesta.status_code)
            raise _FallaHerramientaError(
                "SERVICIO_NO_DISPONIBLE", "El servicio de la plataforma no responde."
            )
        return respuesta.json()


def _fallo(nombre: str, codigo: str, mensaje: str) -> ResultadoHerramienta:
    return ResultadoHerramienta(nombre=nombre, datos={"mensaje": mensaje}, error=codigo)


def _explicar(exc: ValidationError) -> str:
    partes = []
    for error in exc.errors(include_url=False, include_input=False):
        campo = ".".join(str(p) for p in error["loc"])
        partes.append(f"{campo}: {error['msg']}" if campo else error["msg"])
    return "; ".join(partes)


def _parametros(params: Mapping[str, Any] | None) -> dict[str, str | int | float] | None:
    if params is None:
        return None
    return {
        k: str(v) if isinstance(v, date | UUID) else v for k, v in params.items() if v is not None
    }


def _mensaje_de_error(respuesta: httpx.Response) -> str:
    try:
        return str(respuesta.json()["message"])
    except (ValueError, KeyError, TypeError):
        return "La plataforma rechazó la consulta."


def _ids(valores: Any) -> frozenset[UUID]:
    return frozenset(UUID(v) for v in valores)
