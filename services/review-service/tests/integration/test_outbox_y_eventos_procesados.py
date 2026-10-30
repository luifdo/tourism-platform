from collections.abc import Callable
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.entities.elegibilidad_resena import ElegibilidadResena
from app.domain.entities.resena import Resena
from app.domain.value_objects.contenido_resena import ContenidoResena
from app.domain.value_objects.decision_moderacion import DecisionModeracion
from app.infrastructure.observabilidad.contexto_correlacion import fijar_correlation_id
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

AHORA = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
Fabrica = Callable[[], SqlUnidadDeTrabajo]


async def test_el_outbox_guarda_el_sobre_comun(uow: Fabrica, engine: AsyncEngine) -> None:
    """La fixture `engine` valida al final cada sobre contra contracts/events/."""
    fijar_correlation_id("prueba-outbox")
    turista, servicio = uuid4(), uuid4()
    elegible = ElegibilidadResena(
        turista_id=turista, servicio_id=servicio, ultima_visita=date(2026, 11, 14)
    )
    resena, publicada = Resena.escribir(turista, servicio, elegible, ContenidoResena(5), AHORA)
    ocultada = resena.moderar(uuid4(), 1, DecisionModeracion.OCULTAR, "Spam", AHORA)
    assert ocultada is not None
    async with uow() as u:
        await u.resenas.guardar(resena)
        await u.outbox.agregar(publicada)
        await u.outbox.agregar(ocultada)
        await u.confirmar()

    async with engine.connect() as conn:
        filas = (
            await conn.execute(text("SELECT event_type, sobre FROM outbox ORDER BY event_type"))
        ).all()
    assert [tipo for tipo, _ in filas] == ["resena.ocultada", "resena.publicada"]
    sobre = filas[1][1]
    assert sobre["producer"] == "review-service"
    assert sobre["correlation_id"] == "prueba-outbox"
    assert sobre["payload"]["resena_id"] == str(resena.id)
    assert sobre["occurred_at"] == AHORA.isoformat()


async def test_evento_procesado_rechaza_duplicados(uow: Fabrica) -> None:
    event_id: UUID = uuid4()
    async with uow() as u:
        assert await u.eventos_procesados.registrar(event_id, "review.elegibilidad") is True
        assert await u.eventos_procesados.registrar(event_id, "review.elegibilidad") is False
        # Otro consumidor procesa el mismo evento por su cuenta.
        assert await u.eventos_procesados.registrar(event_id, "review.servicios") is True
        await u.confirmar()
    async with uow() as u:
        assert await u.eventos_procesados.ya_procesado(event_id, "review.elegibilidad")
