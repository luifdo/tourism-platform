"""Consumidores `review.elegibilidad` y `review.servicios` contra RabbitMQ y PostgreSQL reales.

`bus` publica como lo harían booking y catalog (validando contra contracts/events/) y
`consumir` da a cada prueba su propia cola con esperas de reintento cortas.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.registrar_dueno_servicio import RegistrarDuenoServicio
from app.application.use_cases.registrar_visita import RegistrarVisita
from app.domain.entities.elegibilidad_resena import ElegibilidadResena
from app.domain.entities.servicio_dueno import ServicioDueno
from app.infrastructure.messaging import manejador_elegibilidad, manejador_servicios
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.manejador_elegibilidad import ManejadorElegibilidad
from app.infrastructure.messaging.manejador_servicios import ManejadorServicios
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from tests.integration.conftest import Bus, Manejar

AHORA = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
Fabrica = Callable[[], SqlUnidadDeTrabajo]
Consumir = Callable[[tuple[str, ...], Manejar], Awaitable[str]]


def sobre(event_type: str, producer: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "version": 1,
        "occurred_at": AHORA.isoformat(),
        "producer": producer,
        "correlation_id": f"corr-{producer}",
        "payload": payload,
    }


def finalizada(turista: UUID, servicio: UUID, fecha: date) -> dict[str, Any]:
    return sobre(
        "reserva.finalizada",
        "booking-service",
        {
            "reserva_id": str(uuid4()),
            "servicio_id": str(servicio),
            "turista_id": str(turista),
            "prestador_id": str(uuid4()),
            "fecha_reserva": fecha.isoformat(),
            "numero_personas": 2,
        },
    )


def publicado(servicio: UUID, dueno: UUID, version: int) -> dict[str, Any]:
    return sobre(
        "servicio.publicado",
        "catalog-service",
        {
            "servicio_id": str(servicio),
            "prestador_id": str(uuid4()),
            "prestador_usuario_id": str(dueno),
            "capacidad_aforo_diario": 40,
            "tarifa_base": 50000,
            "activo": True,
            "version": version,
        },
    )


class Anotador:
    """Envuelve un manejador real y avisa cada vez que termina un evento."""

    def __init__(self, manejar: Manejar) -> None:
        self._manejar = manejar
        self.resultados: asyncio.Queue[ResultadoConsumo] = asyncio.Queue()

    async def __call__(self, s: SobreEvento) -> ResultadoConsumo:
        resultado = await self._manejar(s)
        await self.resultados.put(resultado)
        return resultado

    async def siguiente(self) -> ResultadoConsumo:
        return await asyncio.wait_for(self.resultados.get(), timeout=5)


async def consumidor_elegibilidad(consumir: Consumir, uow: Fabrica) -> Anotador:
    anotador = Anotador(ManejadorElegibilidad(RegistrarVisita(uow)))
    await consumir(manejador_elegibilidad.CLAVES, anotador)
    return anotador


async def consumidor_servicios(consumir: Consumir, uow: Fabrica) -> Anotador:
    anotador = Anotador(ManejadorServicios(RegistrarDuenoServicio(uow)))
    await consumir(manejador_servicios.CLAVES, anotador)
    return anotador


class TestElegibilidad:
    async def test_la_reserva_finalizada_habilita_la_resena(
        self, bus: Bus, consumir: Consumir, uow: Fabrica
    ) -> None:
        anotador = await consumidor_elegibilidad(consumir, uow)
        turista, servicio = uuid4(), uuid4()

        await bus.publicar(finalizada(turista, servicio, date(2026, 11, 14)))

        assert await anotador.siguiente() is ResultadoConsumo.APLICADO
        async with uow() as u:
            assert await u.elegibilidades.obtener(turista, servicio) == ElegibilidadResena(
                turista_id=turista, servicio_id=servicio, ultima_visita=date(2026, 11, 14)
            )

    async def test_guarda_la_visita_mas_reciente(
        self, bus: Bus, consumir: Consumir, uow: Fabrica
    ) -> None:
        anotador = await consumidor_elegibilidad(consumir, uow)
        turista, servicio = uuid4(), uuid4()

        resultados = []
        for fecha in (date(2026, 11, 14), date(2026, 12, 2), date(2026, 10, 1)):
            await bus.publicar(finalizada(turista, servicio, fecha))
            resultados.append(await anotador.siguiente())

        assert resultados == [
            ResultadoConsumo.APLICADO,
            ResultadoConsumo.APLICADO,
            ResultadoConsumo.IGNORADO,
        ]
        async with uow() as u:
            e = await u.elegibilidades.obtener(turista, servicio)
        assert e is not None and e.ultima_visita == date(2026, 12, 2)

    async def test_un_duplicado_se_descarta(
        self, bus: Bus, consumir: Consumir, uow: Fabrica
    ) -> None:
        anotador = await consumidor_elegibilidad(consumir, uow)
        evento = finalizada(uuid4(), uuid4(), date(2026, 11, 14))

        await bus.publicar(evento)
        await bus.publicar(evento)

        assert await anotador.siguiente() is ResultadoConsumo.APLICADO
        assert await anotador.siguiente() is ResultadoConsumo.DUPLICADO

    async def test_un_payload_fuera_de_contrato_va_a_la_dlq(
        self, bus: Bus, consumir: Consumir, uow: Fabrica
    ) -> None:
        await consumidor_elegibilidad(consumir, uow)
        evento = finalizada(uuid4(), uuid4(), date(2026, 11, 14))
        del evento["payload"]["turista_id"]

        await bus.publicar(evento, segun_contrato=False)

        mensaje = await bus.de_la_dlq()
        assert (mensaje.headers or {})["x-intentos"] == 0  # sin reintentos


class TestServicios:
    async def test_registra_el_dueno_y_descarta_versiones_viejas(
        self, bus: Bus, consumir: Consumir, uow: Fabrica
    ) -> None:
        anotador = await consumidor_servicios(consumir, uow)
        servicio, primero, segundo = uuid4(), uuid4(), uuid4()

        resultados = []
        for dueno, version in ((primero, 1), (segundo, 3), (primero, 2), (primero, 3)):
            await bus.publicar(publicado(servicio, dueno, version))
            resultados.append(await anotador.siguiente())

        assert resultados == [
            ResultadoConsumo.APLICADO,
            ResultadoConsumo.APLICADO,
            ResultadoConsumo.IGNORADO,
            ResultadoConsumo.IGNORADO,
        ]
        async with uow() as u:
            assert await u.servicios.obtener(servicio) == ServicioDueno(
                servicio_id=servicio, prestador_usuario_id=segundo, version=3
            )

    async def test_un_servicio_inactivo_conserva_su_dueno(
        self, bus: Bus, consumir: Consumir, uow: Fabrica
    ) -> None:
        anotador = await consumidor_servicios(consumir, uow)
        servicio, dueno = uuid4(), uuid4()
        evento = publicado(servicio, dueno, 1)
        evento["payload"]["activo"] = False

        await bus.publicar(evento)

        assert await anotador.siguiente() is ResultadoConsumo.APLICADO
        async with uow() as u:
            s = await u.servicios.obtener(servicio)
        assert s is not None and s.es_dueno(dueno)
