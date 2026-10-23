"""Paso 5.2b: el repositorio de `servicio_ref` contra Postgres real."""

import asyncio
import random
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from domain.servicio import ServicioRef
from infrastructure.persistence.postgres import RepositorioServiciosPostgres
from infrastructure.persistence.tablas import servicio_ref


def servicio(version: int = 1, aforo: int = 20, servicio_id: UUID | None = None, **cambios) -> ServicioRef:
    datos = dict(
        servicio_id=servicio_id or uuid4(), prestador_id=uuid4(), prestador_usuario_id=uuid4(),
        capacidad_aforo_diario=aforo, tarifa_base=Decimal("85000.50"), activo=True, version=version,
    )
    return ServicioRef(**{**datos, **cambios})


@pytest.fixture
def repo(conexion) -> RepositorioServiciosPostgres:
    return RepositorioServiciosPostgres(conexion)


async def test_leer_uno_que_no_existe_devuelve_none(repo):
    assert await repo.leer(uuid4()) is None


async def test_guarda_uno_nuevo_y_lo_lee_igual(repo):
    s = servicio()
    assert await repo.guardar_si_mas_nuevo(s)
    assert await repo.leer(s.servicio_id) == s


async def test_la_tarifa_vuelve_como_decimal_exacto(repo):
    s = servicio(tarifa_base=Decimal("0.10"))
    await repo.guardar_si_mas_nuevo(s)
    leido = await repo.leer(s.servicio_id)
    assert isinstance(leido.tarifa_base, Decimal) and leido.tarifa_base == Decimal("0.10")


async def test_una_version_mayor_lo_reemplaza(repo):
    s = servicio(version=1)
    await repo.guardar_si_mas_nuevo(s)
    nuevo = servicio(version=2, aforo=8, servicio_id=s.servicio_id, activo=False)
    assert await repo.guardar_si_mas_nuevo(nuevo)
    assert await repo.leer(s.servicio_id) == nuevo


@pytest.mark.parametrize("version", [1, 2], ids=["vieja", "repetida"])
async def test_una_version_igual_o_menor_no_toca_nada(repo, version):
    actual = servicio(version=2, aforo=8)
    await repo.guardar_si_mas_nuevo(actual)
    assert not await repo.guardar_si_mas_nuevo(servicio(version=version, aforo=99, servicio_id=actual.servicio_id))
    assert await repo.leer(actual.servicio_id) == actual


async def test_eventos_en_paralelo_siempre_dejan_la_version_mayor(motor):
    """Diez eventos del mismo servicio, cada uno en su propia transacción y en desorden, todos
    a la vez (como diez réplicas). Al final debe quedar la versión 10, sin importar quién llegue último."""
    servicio_id = uuid4()
    versiones = list(range(1, 11))
    random.shuffle(versiones)

    async def aplicar(version: int) -> bool:
        async with motor.begin() as con:  # cada evento se confirma por separado
            return await RepositorioServiciosPostgres(con).guardar_si_mas_nuevo(
                servicio(version=version, aforo=version, servicio_id=servicio_id)
            )

    try:
        aplicados = await asyncio.gather(*(aplicar(v) for v in versiones))
        async with motor.connect() as con:
            final = await RepositorioServiciosPostgres(con).leer(servicio_id)
        assert final.version == 10 and final.capacidad_aforo_diario == 10
        assert any(aplicados)  # al menos uno se aplicó; los que llegaron tras uno mayor, no
        assert aplicados[versiones.index(10)]  # el 10 siempre se aplica: nadie lo supera
    finally:
        async with motor.begin() as con:
            await con.execute(delete(servicio_ref).where(servicio_ref.c.servicio_id == servicio_id))
