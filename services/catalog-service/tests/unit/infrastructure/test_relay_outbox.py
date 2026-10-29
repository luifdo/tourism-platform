"""Bucle del relay del outbox con dobles: esperas, reintentos con espera creciente y limpieza."""

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.application.dto.estado_outbox import EstadoOutbox
from app.application.dto.evento_pendiente import EventoPendiente
from app.application.dto.resultado_lote import ResultadoLote
from app.application.use_cases.publicar_eventos_pendientes import PublicarEventosPendientes
from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.domain.value_objects.catalogos import ResultadoAuditoria
from app.infrastructure.messaging.relay_outbox import RelayOutbox
from app.infrastructure.observabilidad import metricas_outbox as metricas

AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
LOTE = 3


class RelojMovil:
    def __init__(self) -> None:
        self.momento = AHORA

    def ahora(self) -> datetime:
        return self.momento

    def hoy(self) -> date:
        return self.momento.date()


class OutboxFalso:
    def __init__(self, eventos: int = 0, broker_caido: bool = False) -> None:
        self.pendientes = [
            EventoPendiente(uuid4(), "servicio.publicado", {}, AHORA) for _ in range(eventos)
        ]
        self.broker_caido = broker_caido
        self.limpiezas: list[datetime] = []

    async def procesar_lote(
        self,
        limite: int,
        publicar: Callable[[EventoPendiente], Awaitable[None]],
        ahora: datetime,
    ) -> ResultadoLote:
        publicados = []
        for evento in list(self.pendientes[:limite]):
            try:
                await publicar(evento)
            except ConnectionError:
                return ResultadoLote(tuple(publicados), fallo=True)
            self.pendientes.remove(evento)
            publicados.append(evento.event_type)
        return ResultadoLote(tuple(publicados))

    async def estado(self) -> EstadoOutbox:
        mas_antiguo = AHORA - timedelta(seconds=40) if self.pendientes else None
        return EstadoOutbox(len(self.pendientes), mas_antiguo)

    async def limpiar_publicados(self, antes_de: datetime) -> int:
        self.limpiezas.append(antes_de)
        return 0


class PublicadorFalso:
    def __init__(self, outbox: OutboxFalso) -> None:
        self._outbox = outbox
        self.enviados: list[EventoPendiente] = []

    async def publicar(self, evento: EventoPendiente) -> None:
        if self._outbox.broker_caido:
            raise ConnectionError("RabbitMQ no responde")
        self.enviados.append(evento)


def relay(outbox: OutboxFalso, reloj: RelojMovil | None = None) -> RelayOutbox:
    reloj = reloj or RelojMovil()
    caso = PublicarEventosPendientes(outbox, PublicadorFalso(outbox), reloj, LOTE)
    return RelayOutbox(caso, outbox, reloj, LOTE, 1.0, 30.0, timedelta(days=7))


async def test_lote_lleno_sigue_de_inmediato_y_luego_espera_el_intervalo() -> None:
    outbox = OutboxFalso(eventos=4)
    r = relay(outbox)
    assert await r.una_vuelta(1.0) == 0  # salieron 3 de 3: puede haber más
    assert await r.una_vuelta(0) == 1.0  # salió 1: espera el intervalo
    assert outbox.pendientes == []
    assert metricas.PENDIENTES._value.get() == 0


async def test_broker_caido_duplica_la_espera_hasta_el_maximo() -> None:
    outbox = OutboxFalso(eventos=2, broker_caido=True)
    r = relay(outbox)
    esperas = [1.0]
    for _ in range(6):
        esperas.append(await r.una_vuelta(esperas[-1]))
    assert esperas[1:] == [2.0, 4.0, 8.0, 16.0, 30.0, 30.0]
    assert len(outbox.pendientes) == 2  # nada se pierde
    assert metricas.PENDIENTES._value.get() == 2
    assert metricas.ANTIGUEDAD._value.get() == 40

    outbox.broker_caido = False
    assert await r.una_vuelta(30.0) == 1.0  # al primer lote bueno vuelve al intervalo
    assert outbox.pendientes == []


async def test_error_inesperado_tambien_espera_mas() -> None:
    outbox = OutboxFalso()

    async def falla(*_: object) -> ResultadoLote:
        raise RuntimeError("PostgreSQL no responde")

    outbox.procesar_lote = falla  # type: ignore[method-assign]
    assert await relay(outbox).una_vuelta(4.0) == 8.0


async def test_limpia_una_vez_al_dia_con_la_retencion() -> None:
    outbox, reloj = OutboxFalso(), RelojMovil()
    r = relay(outbox, reloj)
    await r.una_vuelta(1.0)
    reloj.momento += timedelta(hours=5)
    await r.una_vuelta(1.0)
    reloj.momento += timedelta(hours=20)
    await r.una_vuelta(1.0)
    assert outbox.limpiezas == [AHORA - timedelta(days=7), reloj.momento - timedelta(days=7)]


def test_acceso_denegado_cumple_el_contrato_de_auditoria() -> None:
    usuario = uuid4()
    evento = AuditoriaRegistrada(
        usuario_id=usuario,
        accion="ACCESS_DENIED",
        resultado=ResultadoAuditoria.DENEGADO,
        detalles={"rol": "Turista"},
        ip_origen="190.0.0.1",
        ocurrido_en=AHORA,
    )
    assert evento.payload() == {
        "usuario_id": str(usuario),
        "accion": "ACCESS_DENIED",
        "resultado": "DENEGADO",
        "detalles": {"rol": "Turista"},
        "ip_origen": "190.0.0.1",
    }
