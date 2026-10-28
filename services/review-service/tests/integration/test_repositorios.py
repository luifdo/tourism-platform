import asyncio
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.entities.elegibilidad_resena import ElegibilidadResena
from app.domain.entities.reporte_resena import ReporteResena
from app.domain.entities.resena import Resena
from app.domain.entities.servicio_dueno import ServicioDueno
from app.domain.errors import YaReportada, YaResenado
from app.domain.events.resena_publicada import ResenaPublicada
from app.domain.value_objects.aspecto import Aspecto
from app.domain.value_objects.contenido_resena import ContenidoResena
from app.domain.value_objects.decision_moderacion import DecisionModeracion
from app.domain.value_objects.identidad import Rol
from app.domain.value_objects.motivo_reporte import MotivoReporte
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

AHORA = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
Fabrica = Callable[[], SqlUnidadDeTrabajo]


def escribir(
    turista: UUID | None = None, servicio: UUID | None = None
) -> tuple[Resena, ResenaPublicada]:
    elegible = ElegibilidadResena(
        turista_id=turista or uuid4(),
        servicio_id=servicio or uuid4(),
        ultima_visita=date(2026, 11, 14),
    )
    contenido = ContenidoResena(4, {Aspecto.LIMPIEZA: 5}, "Muy limpio")
    return Resena.escribir(elegible.turista_id, elegible.servicio_id, elegible, contenido, AHORA)


def nueva_resena(turista: UUID | None = None, servicio: UUID | None = None) -> Resena:
    return escribir(turista, servicio)[0]


def reporte_de(
    resena: Resena, usuario: UUID | None = None, cuando: datetime = AHORA
) -> ReporteResena:
    return ReporteResena.crear(
        resena.id, usuario or uuid4(), Rol.TURISTA, MotivoReporte.SPAM, None, False, cuando
    )


async def guardar(uow: Fabrica, resena: Resena) -> None:
    async with uow() as u:
        await u.resenas.guardar(resena)
        await u.confirmar()


class TestResenas:
    async def test_sale_igual_a_como_se_guardo(self, uow: Fabrica) -> None:
        r = nueva_resena()
        await guardar(uow, r)

        async with uow() as u:
            leida = await u.resenas.obtener(r.id)
            del_turista = await u.resenas.obtener_de_turista(r.turista_id, r.servicio_id)
        assert leida == r == del_turista

    async def test_sin_respuesta_es_null_de_sql(self, uow: Fabrica, engine: AsyncEngine) -> None:
        """No `null` de JSON: el filtro `sin_respuesta` usa `respuesta IS NULL`."""
        r = nueva_resena()
        await guardar(uow, r)
        async with engine.connect() as conn:
            sin_respuesta = await conn.scalar(
                text("SELECT respuesta IS NULL FROM resena WHERE id = :id"), {"id": r.id}
            )
        assert sin_respuesta is True

    async def test_respuesta_y_estado_en_jsonb(self, uow: Fabrica) -> None:
        r = nueva_resena()
        dueno = uuid4()
        r.responder(
            dueno,
            ServicioDueno(servicio_id=r.servicio_id, prestador_usuario_id=dueno, version=1),
            1,
            "Gracias por venir",
            AHORA,
        )
        r.moderar(uuid4(), 2, DecisionModeracion.OCULTAR, "Spam", AHORA)
        await guardar(uow, r)

        async with uow() as u:
            assert await u.resenas.obtener(r.id) == r

    async def test_una_por_turista_y_servicio(self, uow: Fabrica) -> None:
        primera = nueva_resena()
        await guardar(uow, primera)
        with pytest.raises(YaResenado):
            await guardar(uow, nueva_resena(primera.turista_id, primera.servicio_id))

    async def test_sin_confirmar_no_queda_nada(self, uow: Fabrica, engine: AsyncEngine) -> None:
        r, evento = escribir()
        async with uow() as u:
            await u.resenas.guardar(r)
            await u.outbox.agregar(evento)
        async with engine.connect() as conn:
            assert await conn.scalar(text("SELECT count(*) FROM resena")) == 0
            assert await conn.scalar(text("SELECT count(*) FROM outbox")) == 0


class TestReportes:
    async def test_uno_por_usuario_y_resena(self, uow: Fabrica) -> None:
        r = nueva_resena()
        await guardar(uow, r)
        usuario = uuid4()
        async with uow() as u:
            await u.reportes.agregar(reporte_de(r, usuario))
            await u.confirmar()
        with pytest.raises(YaReportada):
            async with uow() as u:
                await u.reportes.agregar(reporte_de(r, usuario))

    async def test_recientes_y_resolver(self, uow: Fabrica) -> None:
        r, otra = nueva_resena(), nueva_resena()
        await guardar(uow, r)
        await guardar(uow, otra)
        usuario = uuid4()
        async with uow() as u:
            await u.reportes.agregar(reporte_de(r, usuario, AHORA - timedelta(hours=2)))
            await u.reportes.agregar(reporte_de(otra, usuario, AHORA - timedelta(minutes=5)))
            await u.reportes.agregar(reporte_de(r))
            await u.confirmar()

        async with uow() as u:
            recientes = await u.reportes.recientes_de_usuario(usuario, AHORA - timedelta(hours=1))
            assert recientes == [AHORA - timedelta(minutes=5)]
            assert await u.reportes.resolver_abiertos(r.id, AHORA) == 2
            assert await u.reportes.resolver_abiertos(r.id, AHORA) == 0
            await u.confirmar()

    async def test_el_candado_ordena_los_reportes_del_mismo_usuario(self, uow: Fabrica) -> None:
        usuario = uuid4()
        orden: list[str] = []

        async def contar(nombre: str, espera: float) -> None:
            async with uow() as u:
                await u.reportes.recientes_de_usuario(usuario, AHORA - timedelta(hours=1))
                orden.append(f"{nombre}-entra")
                await asyncio.sleep(espera)
                orden.append(f"{nombre}-sale")

        primero = asyncio.create_task(contar("a", 0.3))
        await asyncio.sleep(0.1)
        await contar("b", 0)
        await primero
        assert orden == ["a-entra", "a-sale", "b-entra", "b-sale"]


class TestProyecciones:
    async def test_elegibilidad_se_queda_con_la_visita_mas_reciente(self, uow: Fabrica) -> None:
        turista, servicio = uuid4(), uuid4()
        for visita in (date(2026, 11, 14), date(2026, 10, 1)):
            async with uow() as u:
                await u.elegibilidades.guardar(
                    ElegibilidadResena(
                        turista_id=turista, servicio_id=servicio, ultima_visita=visita
                    )
                )
                await u.confirmar()

        async with uow() as u:
            e = await u.elegibilidades.obtener(turista, servicio)
            assert e is not None and e.ultima_visita == date(2026, 11, 14)
            assert await u.elegibilidades.obtener(turista, uuid4()) is None

    async def test_dueno_descarta_versiones_viejas(self, uow: Fabrica) -> None:
        servicio, nuevo, viejo = uuid4(), uuid4(), uuid4()
        for version, dueno in ((3, nuevo), (2, viejo), (3, viejo)):
            async with uow() as u:
                await u.servicios.guardar(
                    ServicioDueno(servicio_id=servicio, prestador_usuario_id=dueno, version=version)
                )
                await u.confirmar()

        async with uow() as u:
            s = await u.servicios.obtener(servicio)
        assert s == ServicioDueno(servicio_id=servicio, prestador_usuario_id=nuevo, version=3)
