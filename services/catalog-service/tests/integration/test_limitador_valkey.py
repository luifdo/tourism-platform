"""Límite de una llamada por segundo compartido entre réplicas, con Valkey real."""

import asyncio
import time
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from valkey.asyncio import Valkey

from app.infrastructure.clients.limitador_por_segundo import LimitadorPorSegundo

pytestmark = pytest.mark.integration


@pytest.fixture
async def valkey(valkey_url: str) -> AsyncIterator[Valkey]:
    cliente = Valkey.from_url(valkey_url)
    yield cliente
    await cliente.aclose()


async def test_dos_replicas_no_llaman_en_el_mismo_segundo(valkey: Valkey) -> None:
    clave = f"prueba:turno:{uuid4()}"
    replica_a, replica_b = LimitadorPorSegundo(valkey, clave), LimitadorPorSegundo(valkey, clave)
    inicio = time.monotonic()
    tiempos: list[float] = []

    async def llamar(limitador: LimitadorPorSegundo) -> None:
        assert await limitador.turno()
        tiempos.append(time.monotonic() - inicio)

    await asyncio.gather(llamar(replica_a), llamar(replica_b), llamar(replica_a))
    tiempos.sort()
    assert tiempos[0] < 0.3
    assert all(b - a >= 0.95 for a, b in zip(tiempos, tiempos[1:], strict=False))


async def test_si_la_espera_supera_el_maximo_no_hay_turno(valkey: Valkey) -> None:
    clave = f"prueba:turno:{uuid4()}"
    impaciente = LimitadorPorSegundo(valkey, clave, espera_maxima_s=0.2)
    assert await impaciente.turno()
    assert not await impaciente.turno()
