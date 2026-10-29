"""Consumidor `catalog.prestadores` contra RabbitMQ, PostGIS y Valkey reales.

`bus` y `consumir` (conftest) dan a cada prueba su propia cola y esperas de reintento cortas.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from valkey.asyncio import Valkey

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.aplicar_prestador_aprobado import AplicarPrestadorAprobado
from app.application.use_cases.aplicar_prestador_suspendido import AplicarPrestadorSuspendido
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.cache.cache_versionada import CLAVE_GENERACION, CacheVersionada
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.manejador_prestadores import CLAVES, ManejadorPrestadores
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.infrastructure.reloj import RelojSistema

pytestmark = pytest.mark.integration

Sesiones = async_sessionmaker[AsyncSession]
AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)


def sobre(event_type: str, payload: dict[str, Any], **cambios: Any) -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "version": 1,
        "occurred_at": AHORA.isoformat(),
        "producer": "iam-service",
        "correlation_id": "corr-iam",
        "payload": payload,
    } | cambios


def aprobado(prestador: UUID, usuario: UUID, **cambios: Any) -> dict[str, Any]:
    payload = {
        "prestador_id": str(prestador),
        "usuario_id": str(usuario),
        "aprobado_por": str(uuid4()),
        "razon_social": "Minca Viva",
    }
    return sobre("prestador.aprobado", payload, **cambios)


def manejador_real(sesiones: Sesiones, valkey: Valkey) -> ManejadorPrestadores:
    def uow() -> SqlUnidadDeTrabajo:
        return SqlUnidadDeTrabajo(sesiones)

    cache, reloj = CacheVersionada(valkey), RelojSistema()
    return ManejadorPrestadores(
        AplicarPrestadorAprobado(uow, cache, reloj), AplicarPrestadorSuspendido(uow, cache, reloj)
    )


async def esperar(condicion: Callable[[], Awaitable[bool]], segundos: float = 10) -> None:
    for _ in range(int(segundos / 0.1)):
        if await condicion():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("La condición no se cumplió a tiempo")


async def perfil(sesiones: Sesiones, prestador: UUID) -> Any:
    async with sesiones() as session:
        return (
            await session.execute(
                text("SELECT * FROM prestador_perfil WHERE id = :id"), {"id": prestador}
            )
        ).first()


async def contar(sesiones: Sesiones, sql: str) -> int:
    async with sesiones() as session:
        return await session.scalar(text(sql)) or 0


async def test_aprobado_crea_el_perfil_y_el_duplicado_no_cambia_nada(
    sesiones: Sesiones, valkey: Valkey, bus: Any, consumir: Any
) -> None:
    await consumir(CLAVES, manejador_real(sesiones, valkey))
    prestador, usuario = uuid4(), uuid4()
    evento = aprobado(prestador, usuario)
    await bus.publicar(evento)
    await esperar(lambda: _existe(sesiones, prestador))
    fila = await perfil(sesiones, prestador)
    assert (fila.usuario_id, fila.razon_social, fila.activo) == (usuario, "Minca Viva", True)
    assert fila.estado_iam_en == AHORA

    await bus.publicar(evento)  # iam reintenta el mismo evento
    await asyncio.sleep(1)
    assert await contar(sesiones, "SELECT count(*) FROM evento_procesado") == 1
    assert (await perfil(sesiones, prestador)).version == fila.version


async def _existe(sesiones: Sesiones, prestador: UUID) -> bool:
    return await perfil(sesiones, prestador) is not None


async def test_suspendido_apaga_los_servicios_publica_e_invalida_la_cache(
    sesiones: Sesiones, valkey: Valkey, bus: Any, consumir: Any
) -> None:
    p = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Minca Viva")
    servicio = AtractivoServicio.registrar(
        p,
        DatosServicio(
            nombre=TextoTraducido(es="Pozo Azul"),
            descripcion=TextoTraducido(es="Entrada"),
            tipo=TipoServicio.RESERVA_PARQUE,
            ubicacion=Coordenada(lat=11.14, lon=-74.11),
            tarifa_base=Tarifa(Decimal("10000")),
            unidad_tarifa=UnidadTarifa.POR_PERSONA,
            capacidad_aforo_diario=50,
            atributos=AtributosServicio(entrada=BloqueEntrada()),
        ),
        "https://s3/",
        AHORA,
    )
    async with SqlUnidadDeTrabajo(sesiones) as uow:
        await uow.prestadores.guardar(p)
        await uow.servicios.guardar(servicio)
        await uow.confirmar()
    generacion = int(await valkey.get(CLAVE_GENERACION) or 0)

    await consumir(CLAVES, manejador_real(sesiones, valkey))
    await bus.publicar(
        sobre(
            "prestador.suspendido",
            {
                "prestador_id": str(p.id),
                "usuario_id": str(p.usuario_id),
                "suspendido_por": str(uuid4()),
                "motivo": "RNT vencido",
            },
            occurred_at=(AHORA + timedelta(hours=1)).isoformat(),
        )
    )

    async def apagado() -> bool:
        return not (await perfil(sesiones, p.id)).activo

    await esperar(apagado)
    async with sesiones() as session:
        fila = (
            await session.execute(
                text("SELECT activo, desactivado_por_suspension FROM atractivo_servicio")
            )
        ).one()
        [publicado] = list(
            await session.scalars(
                text("SELECT sobre FROM outbox WHERE event_type = 'servicio.publicado'")
            )
        )
    assert (fila.activo, fila.desactivado_por_suspension) == (False, True)
    assert publicado["payload"]["activo"] is False
    assert publicado["correlation_id"] == "corr-iam"  # la correlación sigue de iam a booking
    assert int(await valkey.get(CLAVE_GENERACION) or 0) == generacion + 1


async def test_fallo_transitorio_se_reintenta_y_se_aplica(
    sesiones: Sesiones, valkey: Valkey, bus: Any, consumir: Any
) -> None:
    real, llamadas = manejador_real(sesiones, valkey), []

    async def falla_dos_veces(s: SobreEvento) -> ResultadoConsumo:
        llamadas.append(s.event_id)
        if len(llamadas) <= 2:
            raise ConnectionError("PostgreSQL no responde")
        return await real(s)

    await consumir(CLAVES, falla_dos_veces)
    prestador = uuid4()
    await bus.publicar(aprobado(prestador, uuid4()))
    await esperar(lambda: _existe(sesiones, prestador))
    assert len(llamadas) == 3 and len(set(llamadas)) == 1


async def test_tras_agotar_los_reintentos_va_a_la_dlq(bus: Any, consumir: Any) -> None:
    llamadas = []

    async def siempre_falla(s: SobreEvento) -> ResultadoConsumo:
        llamadas.append(1)
        raise ConnectionError("PostgreSQL no responde")

    await consumir(CLAVES, siempre_falla)
    await bus.publicar(aprobado(uuid4(), uuid4()))
    mensaje = await bus.de_la_dlq()
    cabeceras = mensaje.headers or {}
    assert len(llamadas) == 4  # el intento original y 3 reintentos
    assert cabeceras["x-intentos"] == 4
    assert str(cabeceras["x-cola"]).startswith("prueba.")
    assert "ConnectionError" in str(cabeceras["x-error"])
    assert mensaje.routing_key == "prestador.aprobado"


@pytest.mark.parametrize(
    "cuerpo",
    [
        sobre("prestador.aprobado", {"prestador_id": "no-es-uuid"}),
        sobre("prestador.aprobado", {}, version=2),
        {"esto": "no es un sobre", "event_type": "prestador.aprobado"},
    ],
    ids=["payload_invalido", "version_desconocida", "sin_sobre"],
)
async def test_un_mensaje_invalido_va_directo_a_la_dlq(
    sesiones: Sesiones, valkey: Valkey, bus: Any, consumir: Any, cuerpo: dict
) -> None:
    await consumir(CLAVES, manejador_real(sesiones, valkey))
    await bus.publicar(cuerpo, segun_contrato=False)  # roto a propósito
    mensaje = await bus.de_la_dlq()
    assert (mensaje.headers or {})["x-intentos"] == 0
    assert await contar(sesiones, "SELECT count(*) FROM prestador_perfil") == 0
