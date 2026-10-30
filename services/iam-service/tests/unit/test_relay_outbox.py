"""Bucle del relay: espera creciente, lote lleno, métricas y limpieza diaria (C-09)."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from prometheus_client import REGISTRY

from app.application.dto.estado_outbox import EstadoOutbox
from app.application.dto.evento_pendiente import EventoPendiente
from app.application.dto.resultado_lote import ResultadoLote
from app.application.use_cases.publicar_eventos_pendientes import PublicarEventosPendientes
from app.infrastructure.messaging.relay_outbox import RelayOutbox
from tests.fakes import AHORA


class OutboxFalso:
    def __init__(self, resultados: list[ResultadoLote | Exception]) -> None:
        self.resultados = resultados
        self.limpiezas: list[datetime] = []
        self.pendientes = EstadoOutbox(pendientes=2, mas_antiguo=AHORA - timedelta(seconds=30))

    async def procesar_lote(
        self, limite: int, publicar: Callable[[EventoPendiente], Awaitable[None]], ahora: datetime
    ) -> ResultadoLote:
        resultado = self.resultados.pop(0)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    async def estado(self) -> EstadoOutbox:
        return self.pendientes

    async def limpiar_publicados(self, antes_de: datetime) -> int:
        self.limpiezas.append(antes_de)
        return 0


class PublicadorNulo:
    async def publicar(self, evento: EventoPendiente) -> None:
        pass


def relay(outbox: OutboxFalso, lote: int = 2) -> RelayOutbox:
    def reloj() -> datetime:
        return AHORA

    return RelayOutbox(
        publicar=PublicarEventosPendientes(outbox, PublicadorNulo(), reloj, lote),
        outbox=outbox,
        reloj=reloj,
        lote=lote,
        intervalo_segundos=1.0,
        espera_maxima_segundos=8.0,
        retencion=timedelta(days=7),
    )


def publicados(event_type: str) -> float:
    valor = REGISTRY.get_sample_value("iam_eventos_publicados_total", {"event_type": event_type})
    return valor or 0.0


async def test_lote_lleno_sigue_de_inmediato_y_parcial_espera_el_intervalo() -> None:
    lleno = ResultadoLote(publicados=("prestador.suspendido", "prestador.suspendido"))
    outbox = OutboxFalso([lleno, ResultadoLote(publicados=("prestador.suspendido",))])
    r = relay(outbox)
    antes = publicados("prestador.suspendido")

    assert await r.una_vuelta(1.0) == 0
    assert await r.una_vuelta(1.0) == 1.0
    assert publicados("prestador.suspendido") == antes + 3
    assert REGISTRY.get_sample_value("iam_outbox_pendientes") == 2
    assert REGISTRY.get_sample_value("iam_outbox_antiguedad_segundos") == 30


async def test_fallos_duplican_la_espera_hasta_el_maximo() -> None:
    outbox = OutboxFalso(
        [ConnectionError("PostgreSQL"), ResultadoLote(fallo=True)] * 3 + [ResultadoLote()]
    )
    r = relay(outbox)

    esperas = []
    espera = 1.0
    for _ in range(7):
        espera = await r.una_vuelta(espera)
        esperas.append(espera)

    assert esperas == [2.0, 4.0, 8.0, 8.0, 8.0, 8.0, 1.0]


async def test_limpia_una_vez_al_dia() -> None:
    outbox = OutboxFalso([ResultadoLote(), ResultadoLote()])
    r = relay(outbox)

    await r.una_vuelta(1.0)
    await r.una_vuelta(1.0)

    assert outbox.limpiezas == [AHORA - timedelta(days=7)]
