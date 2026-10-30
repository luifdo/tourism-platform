"""Rutas REST del booking-service (contracts/openapi/booking.yaml).

Cada ruta traduce HTTP ↔ caso de uso; las reglas viven en domain/ y application/.
"""

from datetime import date
from typing import Annotated, Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from application.calendario import (
    AbrirRangoCalendario,
    ConsultarCalendario,
    ConsultarDisponibilidad,
    GuardarDiaCalendario,
)
from application.consultas import ListarReservas, ObtenerReserva
from application.errores import FaltaIfMatch, PeticionEnProceso
from application.ports import FiltroReservas, RespuestaGuardada
from application.reservas import (
    CancelarReserva,
    ConfirmarReserva,
    ModificarReserva,
    RechazarReserva,
    SolicitarReserva,
)
from domain.errores import Validacion
from domain.reserva import Actor, EstadoReserva, Reserva
from infrastructure.http import esquemas as e
from infrastructure.http.errores import correlation_id
from infrastructure.http.identidad import Identidad, Prestador, Rol, Turista, TuristaOPrestador

router = APIRouter(prefix="/api/bookings")

ERRORES = {
    400: {"model": e.Error, "description": "`VALIDACION`"},
    401: {"model": e.Error, "description": "`NO_AUTENTICADO`: faltan X-Usuario-Id o X-Usuario-Rol"},
    403: {"model": e.Error, "description": "`ROL_NO_PERMITIDO` (queda en la bitácora)"},
    404: {"model": e.Error, "description": "`NO_ENCONTRADO`: no existe o no le pertenece"},
    409: {"model": e.Error, "description": "Conflicto de estado, cupos o versión"},
}

IdempotencyKey = Annotated[
    str | None,
    Header(description="Clave única por intento de envío; un reintento con la misma clave no repite la operación (48 h)."),
]


def _ctx(request: Request):
    return request.app.state.contenedor.ctx


def _etag(version: int) -> dict[str, str]:
    return {"ETag": f'"{version}"'}


def _version(if_match: str | None) -> int | None:
    if if_match is None:
        return None
    valor = if_match.strip().removeprefix("W/").strip('"')
    try:
        return int(valor)
    except ValueError as exc:
        raise Validacion("If-Match debe ser la versión que devolvió el ETag, p. ej. \"3\".") from exc


def _reserva(r: Reserva, estado: int = 200) -> JSONResponse:
    return JSONResponse(jsonable_encoder(e.ReservaSalida.de(r)), status_code=estado, headers=_etag(r.version))


async def _idempotente(
    request: Request, quien: Identidad, clave: str | None, accion: Callable[[], Awaitable[Response]]
) -> Response:
    """Guía §6.3: la primera petición con una clave la reserva y se ejecuta; un reintento recibe
    la misma respuesta sin repetir la operación, o 409 si la primera todavía no terminó."""
    if not clave:
        return await accion()
    almacen = request.app.state.contenedor.idempotencia
    llave = f"idem:booking:{quien.usuario_id}:{request.method}:{request.url.path}:{clave}"
    if not await almacen.reservar(llave):
        if guardada := await almacen.obtener(llave):
            return Response(guardada.cuerpo, status_code=guardada.estado, headers=guardada.headers,
                            media_type="application/json")
        raise PeticionEnProceso("Ya se está procesando una petición con esta Idempotency-Key; reintente en unos segundos.")
    try:
        respuesta = await accion()
    except BaseException:
        await almacen.liberar(llave)  # un error de negocio o inesperado no deja la clave tomada
        raise
    if 200 <= respuesta.status_code < 300:
        headers = {k: v for k, v in respuesta.headers.items() if k.lower() == "etag"}
        await almacen.guardar(llave, RespuestaGuardada(respuesta.status_code, bytes(respuesta.body), headers))
    else:
        await almacen.liberar(llave)
    return respuesta


# ---------- Disponibilidad (pública) ----------

@router.get("/disponibilidad", tags=["Disponibilidad"], response_model=e.Disponibilidad,
            summary="Consultar disponibilidad de un servicio (UC10)", responses={400: ERRORES[400]})
async def consultar_disponibilidad(
    request: Request,
    servicio_id: UUID,
    desde: date,
    hasta: Annotated[date, Query(description="Máximo 62 días después de `desde`.")],
):
    dias = await ConsultarDisponibilidad(_ctx(request))(servicio_id, desde, hasta)
    return e.Disponibilidad(
        servicio_id=servicio_id,
        dias=[e.DiaDisponible(fecha=d.fecha, cupos_disponibles=d.cupos_disponibles, tarifa_dia=d.tarifa_dia) for d in dias],
    )


# ---------- Turista ----------

@router.post("", tags=["Turista"], status_code=201, response_model=e.ReservaSalida,
             summary="Solicitar una reserva (UC11)", responses=ERRORES)
@router.post("/", include_in_schema=False, status_code=201)
async def solicitar_reserva(
    request: Request, quien: Turista, cuerpo: e.SolicitudReservaCrear, idempotency_key: IdempotencyKey = None
):
    async def accion() -> Response:
        r = await SolicitarReserva(_ctx(request))(
            quien.usuario_id, cuerpo.servicio_id, cuerpo.fecha_reserva, cuerpo.numero_personas,
            correlation_id(request),
        )
        return _reserva(r, 201)

    return await _idempotente(request, quien, idempotency_key, accion)


@router.get("/mis-reservas", tags=["Turista"], response_model=e.PaginaReservas,
            summary="Historial de reservas del turista (UC13)", responses=ERRORES)
async def mis_reservas(
    request: Request,
    quien: Turista,
    estado: EstadoReserva | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 20,
):
    filtro = FiltroReservas(turista_id=quien.usuario_id, estado=estado)
    items, total = await ListarReservas(_ctx(request))(filtro, pagina, tamano)
    return e.PaginaReservas(items=[e.ReservaSalida.de(r) for r in items], pagina=pagina, tamano=tamano, total=total)


# ---------- Prestador ----------

@router.get("/prestador/solicitudes", tags=["Prestador"], response_model=e.PaginaReservas,
            summary="Panel de solicitudes del prestador (UC20)", responses=ERRORES)
async def solicitudes_prestador(
    request: Request,
    quien: Prestador,
    estado: Annotated[EstadoReserva | None, Query(description="Por defecto, SOLICITADA.")] = None,
    servicio_id: UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 20,
):
    estado = estado or EstadoReserva.SOLICITADA
    filtro = FiltroReservas(
        prestador_usuario_id=quien.usuario_id, estado=estado, servicio_id=servicio_id, desde=desde, hasta=hasta,
        orden="expira_en" if estado is EstadoReserva.SOLICITADA else "recientes",
    )
    items, total = await ListarReservas(_ctx(request))(filtro, pagina, tamano)
    return e.PaginaReservas(items=[e.ReservaSalida.de(r) for r in items], pagina=pagina, tamano=tamano, total=total)


@router.get("/prestador/calendario/{servicio_id}", tags=["Prestador"], response_model=e.Calendario,
            summary="Calendario de cupos y tarifas (UC19)", responses=ERRORES)
async def calendario(request: Request, quien: Prestador, servicio_id: UUID, desde: date, hasta: date):
    dias = await ConsultarCalendario(_ctx(request))(quien.usuario_id, servicio_id, desde, hasta)
    return e.Calendario(servicio_id=servicio_id, dias=[e.DiaCalendario.de(d) for d in dias])


@router.post("/prestador/calendario/{servicio_id}/rango", tags=["Prestador"], status_code=201,
             response_model=e.ResultadoRango, summary="Abrir un rango de días (UC19)",
             responses={**ERRORES, 422: {"model": e.Error, "description": "`SUPERA_AFORO`"}})
async def abrir_rango(
    request: Request, quien: Prestador, servicio_id: UUID, cuerpo: e.RangoCalendario,
    idempotency_key: IdempotencyKey = None,
):
    async def accion() -> Response:
        creados, omitidos = await AbrirRangoCalendario(_ctx(request))(
            quien.usuario_id, servicio_id, cuerpo.desde, cuerpo.hasta, cuerpo.cupos_totales,
            cuerpo.tarifa_dia, set(cuerpo.dias_semana) if cuerpo.dias_semana else None,
        )
        return JSONResponse(jsonable_encoder(e.ResultadoRango(creados=creados, omitidos=omitidos)), status_code=201)

    return await _idempotente(request, quien, idempotency_key, accion)


@router.put("/prestador/calendario/{servicio_id}/{fecha}", tags=["Prestador"], response_model=e.DiaCalendario,
            summary="Crear o editar un día del calendario (UC19)",
            description="Sin `If-Match` solo crea el día. Con `If-Match` (el `ETag` recibido) edita si la versión coincide.",
            responses={**ERRORES, 201: {"model": e.DiaCalendario, "description": "Día creado"},
                       422: {"model": e.Error, "description": "`SUPERA_AFORO`"}})
async def guardar_dia(
    request: Request, quien: Prestador, servicio_id: UUID, fecha: date, cuerpo: e.DiaCalendarioGuardar,
    if_match: Annotated[str | None, Header(description="Versión (`ETag`) del día que se editó.")] = None,
    idempotency_key: IdempotencyKey = None,
):
    async def accion() -> Response:
        dia, creado = await GuardarDiaCalendario(_ctx(request))(
            quien.usuario_id, servicio_id, fecha, cuerpo.cupos_totales, cuerpo.tarifa_dia, _version(if_match)
        )
        return JSONResponse(
            jsonable_encoder(e.DiaCalendario.de(dia)), status_code=201 if creado else 200, headers=_etag(dia.version)
        )

    return await _idempotente(request, quien, idempotency_key, accion)


# ---------- Una reserva (al final: /{reserva_id} no debe tapar las rutas anteriores) ----------

@router.get("/{reserva_id}", tags=["Turista", "Prestador"], response_model=e.ReservaSalida,
            summary="Detalle de una reserva", responses=ERRORES)
async def obtener_reserva(request: Request, quien: TuristaOPrestador, reserva_id: UUID):
    return _reserva(await ObtenerReserva(_ctx(request))(quien.usuario_id, reserva_id))


@router.patch("/{reserva_id}", tags=["Turista"], response_model=e.ReservaSalida,
              summary="Modificar una reserva (UC12)",
              description="Solo en `SOLICITADA`. Requiere `If-Match` con el `ETag` de la reserva.",
              responses={**ERRORES, 428: {"model": e.Error, "description": "`FALTA_IF_MATCH`"}})
async def modificar_reserva(
    request: Request, quien: Turista, reserva_id: UUID, cuerpo: e.SolicitudReservaModificar,
    if_match: Annotated[str | None, Header(description="Versión (`ETag`) de la reserva.")] = None,
):
    version = _version(if_match)
    if version is None:
        raise FaltaIfMatch("Envíe If-Match con la versión (ETag) de la reserva.")
    r = await ModificarReserva(_ctx(request))(
        quien.usuario_id, reserva_id, version, cuerpo.fecha_reserva, cuerpo.numero_personas, correlation_id(request)
    )
    return _reserva(r)


@router.post("/{reserva_id}/cancelar", tags=["Turista", "Prestador"], response_model=e.ReservaSalida,
             summary="Cancelar una reserva (UC12)", responses=ERRORES)
async def cancelar_reserva(
    request: Request, quien: TuristaOPrestador, reserva_id: UUID, cuerpo: e.Motivo | None = None
):
    actor = Actor.TURISTA if quien.rol is Rol.TURISTA else Actor.PRESTADOR
    r = await CancelarReserva(_ctx(request))(
        actor, quien.usuario_id, reserva_id, cuerpo.motivo if cuerpo else None, correlation_id(request)
    )
    return _reserva(r)


@router.post("/{reserva_id}/confirmar", tags=["Prestador"], response_model=e.ReservaSalida,
             summary="Confirmar una solicitud (UC20)", responses=ERRORES)
async def confirmar_reserva(request: Request, quien: Prestador, reserva_id: UUID):
    return _reserva(await ConfirmarReserva(_ctx(request))(quien.usuario_id, reserva_id, correlation_id(request)))


@router.post("/{reserva_id}/rechazar", tags=["Prestador"], response_model=e.ReservaSalida,
             summary="Rechazar una solicitud (UC20)", responses=ERRORES)
async def rechazar_reserva(request: Request, quien: Prestador, reserva_id: UUID, cuerpo: e.MotivoObligatorio):
    r = await RechazarReserva(_ctx(request))(quien.usuario_id, reserva_id, cuerpo.motivo, correlation_id(request))
    return _reserva(r)
