"""Consumidor `catalog.calificaciones` contra RabbitMQ y PostGIS reales: el promedio que ve la
búsqueda cuenta solo las reseñas visibles.

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

from app.application.dto.criterios_busqueda import CriteriosBusqueda
from app.application.use_cases.aplicar_evento_resena import AplicarEventoResena
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.messaging.manejador_calificaciones import (
    CLAVES,
    ManejadorCalificaciones,
)
from app.infrastructure.persistence.consultas.sql_consulta_servicios import SqlConsultaServicios
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

pytestmark = pytest.mark.integration

Sesiones = async_sessionmaker[AsyncSession]
AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)


def evento(
    tipo: str, resena_id: UUID, servicio_id: UUID, puntuacion: int, minutos: int = 0
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "resena_id": str(resena_id),
        "servicio_id": str(servicio_id),
        "turista_id": str(uuid4()),
        "puntuacion": puntuacion,
    }
    if tipo == "ocultada":
        payload |= {"moderada_por": str(uuid4()), "motivo": "Lenguaje ofensivo"}
    return {
        "event_id": str(uuid4()),
        "event_type": f"resena.{tipo}",
        "version": 1,
        "occurred_at": (AHORA + timedelta(minutes=minutos)).isoformat(),
        "producer": "review-service",
        "payload": payload,
    }


@pytest.fixture
async def servicio_id(sesiones: Sesiones) -> UUID:
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Minca Viva")
    servicio = AtractivoServicio.registrar(
        perfil,
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
        await uow.prestadores.guardar(perfil)
        await uow.servicios.guardar(servicio)
        await uow.confirmar()
    return servicio.id


def manejador(sesiones: Sesiones) -> ManejadorCalificaciones:
    return ManejadorCalificaciones(AplicarEventoResena(lambda: SqlUnidadDeTrabajo(sesiones)))


async def esperar(condicion: Callable[[], Awaitable[bool]], segundos: float = 10) -> None:
    for _ in range(int(segundos / 0.1)):
        if await condicion():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("La condición no se cumplió a tiempo")


async def procesados(sesiones: Sesiones) -> int:
    async with sesiones() as session:
        return await session.scalar(text("SELECT count(*) FROM evento_procesado")) or 0


async def publicar_y_esperar(bus: Any, sesiones: Sesiones, *eventos: dict[str, Any]) -> None:
    antes = await procesados(sesiones)
    for e in eventos:
        await bus.publicar(e)

    async def listos() -> bool:
        return await procesados(sesiones) >= antes + len(eventos)

    await esperar(listos)


async def en_la_busqueda(sesiones: Sesiones) -> tuple[float | None, int]:
    [item] = (
        await SqlConsultaServicios(sesiones).buscar(CriteriosBusqueda(idioma=Idioma.ES))
    ).items
    return item.calificacion_promedio, item.total_resenas


async def test_el_promedio_cuenta_solo_las_resenas_visibles(
    sesiones: Sesiones, servicio_id: UUID, bus: Any, consumir: Any
) -> None:
    await consumir(CLAVES, manejador(sesiones))
    buena, regular, falsa = uuid4(), uuid4(), uuid4()
    await publicar_y_esperar(
        bus,
        sesiones,
        evento("publicada", buena, servicio_id, 5),
        evento("publicada", regular, servicio_id, 3),
        evento("publicada", falsa, servicio_id, 1),
    )
    assert await en_la_busqueda(sesiones) == (3.0, 3)

    # El Administrador oculta la reseña falsa: deja de contar.
    await publicar_y_esperar(bus, sesiones, evento("ocultada", falsa, servicio_id, 1, minutos=1))
    assert await en_la_busqueda(sesiones) == (4.0, 2)

    # Se vuelve a publicar tras revisarla: vuelve a contar, sin duplicarse.
    await publicar_y_esperar(bus, sesiones, evento("publicada", falsa, servicio_id, 1, minutos=2))
    assert await en_la_busqueda(sesiones) == (3.0, 3)


async def test_la_misma_resena_repetida_no_cuenta_doble(
    sesiones: Sesiones, servicio_id: UUID, bus: Any, consumir: Any
) -> None:
    await consumir(CLAVES, manejador(sesiones))
    r = uuid4()
    # Review la vuelve a publicar con otro event_id (UC29): misma fila.
    await publicar_y_esperar(
        bus,
        sesiones,
        evento("publicada", r, servicio_id, 4),
        evento("publicada", r, servicio_id, 4, minutos=1),
    )
    assert await en_la_busqueda(sesiones) == (4.0, 1)


async def test_puntuacion_fuera_de_rango_va_a_la_dlq(
    sesiones: Sesiones, servicio_id: UUID, bus: Any, consumir: Any
) -> None:
    await consumir(CLAVES, manejador(sesiones))
    await bus.publicar(evento("publicada", uuid4(), servicio_id, 6), segun_contrato=False)  # 1..5
    mensaje = await bus.de_la_dlq()
    assert mensaje.routing_key == "resena.publicada"
    assert await en_la_busqueda(sesiones) == (None, 0)
