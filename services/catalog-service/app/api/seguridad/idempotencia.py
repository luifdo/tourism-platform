"""`Idempotency-Key` (Plan §6.8): un reenvío de la PWA devuelve la misma respuesta sin repetir.

La clave se guarda por usuario, método y ruta: otro usuario con la misma clave (o la misma
clave en otra operación) no puede leer ni reutilizar una respuesta ajena. Solo se guardan
las respuestas exitosas; si la operación falla, el reintento vuelve a ejecutarse.
"""

from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.application.dto.respuesta_guardada import RespuestaGuardada
from app.application.errores import SolicitudEnProceso
from app.application.ports.almacen_idempotencia import AlmacenIdempotencia
from app.domain.value_objects.identidad import Identidad

CABECERA_REPETIDA = "Idempotent-Replayed"
_CABECERAS_GUARDADAS = ("etag", "content-language", "location")


async def responder_idempotente(
    almacen: AlmacenIdempotencia,
    request: Request,
    identidad: Identidad,
    clave: UUID | None,
    ejecutar: Callable[[], Awaitable[JSONResponse]],
) -> Response:
    if clave is None:
        return await ejecutar()
    llave = f"idem:catalog:{identidad.usuario_id}:{request.method}:{request.url.path}:{clave}"
    reserva = await almacen.reservar(llave)
    if isinstance(reserva, RespuestaGuardada):
        return Response(
            content=reserva.cuerpo,
            status_code=reserva.estado,
            headers=reserva.cabeceras | {CABECERA_REPETIDA: "true"},
            media_type="application/json",
        )
    if reserva is False:
        raise SolicitudEnProceso()
    try:
        respuesta = await ejecutar()
    except BaseException:
        await almacen.liberar(llave)
        raise
    cabeceras = {k: v for k, v in respuesta.headers.items() if k in _CABECERAS_GUARDADAS}
    await almacen.guardar(
        llave, RespuestaGuardada(respuesta.status_code, bytes(respuesta.body), cabeceras)
    )
    return respuesta
