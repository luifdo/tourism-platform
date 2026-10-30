"""Estados de una Idempotency-Key en el almacén en memoria (Guía §6.3)."""

from application.ports import RespuestaGuardada
from infrastructure.persistence.idempotencia_memoria import AlmacenIdempotenciaMemoria

RESPUESTA = RespuestaGuardada(201, b'{"id": "r1"}', {"etag": '"1"'})


async def test_solo_la_primera_peticion_reserva_la_clave():
    almacen = AlmacenIdempotenciaMemoria()
    assert await almacen.reservar("k") is True
    assert await almacen.reservar("k") is False
    assert await almacen.obtener("k") is None  # en proceso: todavía no hay respuesta


async def test_guardar_deja_la_respuesta_para_los_reintentos():
    almacen = AlmacenIdempotenciaMemoria()
    await almacen.reservar("k")
    await almacen.guardar("k", RESPUESTA)
    assert await almacen.reservar("k") is False
    assert await almacen.obtener("k") == RESPUESTA


async def test_liberar_permite_ejecutar_de_nuevo():
    almacen = AlmacenIdempotenciaMemoria()
    await almacen.reservar("k")
    await almacen.liberar("k")
    assert await almacen.reservar("k") is True


async def test_la_marca_en_proceso_vence_sola():
    almacen = AlmacenIdempotenciaMemoria(ttl_en_proceso=0)  # como si el pod hubiera muerto a medias
    await almacen.reservar("k")
    assert await almacen.reservar("k") is True
