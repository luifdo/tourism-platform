import asyncio
from datetime import timedelta
from uuid import uuid4

from src.domain.conversacion import Conversacion, Mensaje, Rol
from src.infrastructure.persistence.sesiones_valkey import PREFIJO, SesionesValkey


def _conversacion_con_mensajes(n: int) -> Conversacion:
    conversacion = Conversacion.nueva(uuid4())
    for i in range(n):
        rol = Rol.TURISTA if i % 2 == 0 else Rol.ASISTENTE
        conversacion.agregar(Mensaje(rol=rol, texto=f"mensaje {i} — ñandú"))
    return conversacion


async def test_guarda_y_recupera_la_conversacion(valkey):
    sesiones = SesionesValkey(valkey)
    conversacion = _conversacion_con_mensajes(3)

    await sesiones.guardar(conversacion)

    assert await sesiones.obtener(conversacion.id) == conversacion


async def test_guarda_solo_los_ultimos_10_mensajes(valkey):
    sesiones = SesionesValkey(valkey)
    conversacion = _conversacion_con_mensajes(14)

    await sesiones.guardar(conversacion)

    recuperada = await sesiones.obtener(conversacion.id)
    assert len(recuperada.mensajes) == 10
    assert recuperada.mensajes[0].texto == "mensaje 4 — ñandú"


async def test_conversacion_inexistente_devuelve_none(valkey):
    assert await SesionesValkey(valkey).obtener(uuid4()) is None


async def test_la_sesion_dura_24_horas_y_cada_guardado_las_renueva(valkey):
    sesiones = SesionesValkey(valkey)
    conversacion = _conversacion_con_mensajes(1)
    llave = PREFIJO + str(conversacion.id)

    await sesiones.guardar(conversacion)
    await valkey.expire(llave, 60)
    await sesiones.guardar(conversacion)

    assert 24 * 3600 - 5 <= await valkey.ttl(llave) <= 24 * 3600


async def test_la_sesion_expira_con_el_ttl(valkey):
    sesiones = SesionesValkey(valkey, ttl=timedelta(seconds=1))
    conversacion = _conversacion_con_mensajes(1)
    await sesiones.guardar(conversacion)

    await asyncio.sleep(1.5)

    assert await sesiones.obtener(conversacion.id) is None
