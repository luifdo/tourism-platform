"""Correos de reservas de punta a punta: RabbitMQ → consumidor → PostGIS → SMTP (Mailpit real).

iam todavía no tiene su ruta de contacto: el directorio es un doble. `bus` y `consumir`
(conftest) dan a cada prueba su propia cola.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.contacto_usuario import ContactoUsuario
from app.application.use_cases.notificar_reserva import NotificarReserva
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
from app.infrastructure.messaging.manejador_notificaciones import (
    CLAVES,
    ManejadorNotificaciones,
)
from app.infrastructure.notificaciones.enviador_smtp import EnviadorSmtp
from app.infrastructure.notificaciones.redactor_correos_jinja import RedactorCorreosJinja
from app.infrastructure.persistence.consultas.sql_consulta_prestador import SqlConsultaPrestador
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

pytestmark = pytest.mark.integration

Sesiones = async_sessionmaker[AsyncSession]
AHORA = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
TURISTA = uuid4()


class DirectorioFalso:
    def __init__(self, prestador_usuario_id: UUID) -> None:
        self._prestador = prestador_usuario_id

    async def contacto(self, usuario_id: UUID) -> ContactoUsuario | None:
        if usuario_id == TURISTA:
            return ContactoUsuario(usuario_id, "Ana", "ana@correo.test", Idioma.EN)
        if usuario_id == self._prestador:
            return ContactoUsuario(usuario_id, "Sierra Viva", "sierra@correo.test", Idioma.ES)
        return None


@pytest.fixture
async def servicio(sesiones: Sesiones) -> AtractivoServicio:
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Sierra Viva")
    s = AtractivoServicio.registrar(
        perfil,
        DatosServicio(
            nombre=TextoTraducido(es="Pozo Azul", en="Blue Pool"),
            descripcion=TextoTraducido(es="Entrada"),
            tipo=TipoServicio.RESERVA_PARQUE,
            ubicacion=Coordenada(lat=11.1426, lon=-74.1178),
            tarifa_base=Tarifa(Decimal("10000")),
            unidad_tarifa=UnidadTarifa.POR_PERSONA,
            capacidad_aforo_diario=20,
            atributos=AtributosServicio(entrada=BloqueEntrada()),
        ),
        "https://s3/",
        AHORA,
    )
    async with SqlUnidadDeTrabajo(sesiones) as uow:
        await uow.prestadores.guardar(perfil)
        await uow.servicios.guardar(s)
        await uow.confirmar()
    return s


@pytest.fixture
async def buzon(mailpit: dict[str, Any]) -> Any:
    async with httpx.AsyncClient(base_url=mailpit["api"]) as api:
        await api.delete("/messages")  # cada prueba empieza con el buzón vacío
        yield api


def evento(tipo: str, s: AtractivoServicio, **extra: Any) -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": f"reserva.{tipo}",
        "version": 1,
        "occurred_at": AHORA.isoformat(),
        "producer": "booking-service",
        "payload": {
            "reserva_id": str(uuid4()),
            "servicio_id": str(s.id),
            "turista_id": str(TURISTA),
            "prestador_id": str(s.prestador_id),
            "fecha_reserva": "2026-11-05",
            "numero_personas": 2,
        }
        | extra,
    }


async def esperar(condicion: Callable[[], Awaitable[bool]], segundos: float = 10) -> None:
    for _ in range(int(segundos / 0.1)):
        if await condicion():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("La condición no se cumplió a tiempo")


async def mensajes(buzon: httpx.AsyncClient) -> list[dict]:
    return (await buzon.get("/messages")).json()["messages"]


async def test_confirmacion_y_rechazo_llegan_al_turista_en_su_idioma(
    sesiones: Sesiones,
    servicio: AtractivoServicio,
    mailpit: dict,
    buzon: Any,
    bus: Any,
    consumir: Any,
) -> None:
    notificar = NotificarReserva(
        lambda: SqlUnidadDeTrabajo(sesiones),
        SqlConsultaPrestador(sesiones),
        DirectorioFalso(servicio.prestador_usuario_id),
        RedactorCorreosJinja(),
        EnviadorSmtp(
            mailpit["host"], mailpit["smtp"], "Turismo <no-responder@t.local>", None, None, False, 5
        ),
    )
    await consumir(CLAVES, ManejadorNotificaciones(notificar))

    confirmada = evento("confirmada", servicio)
    await bus.publicar(confirmada)
    await bus.publicar(confirmada)  # booking reintenta: no se reenvía
    await bus.publicar(evento("rechazada", servicio, motivo="Plazo de respuesta vencido"))
    await bus.publicar(evento("solicitada", servicio))
    # Como lo publica booking según el contrato: el rol de quien canceló, no su id.
    await bus.publicar(
        evento("cancelada", servicio, cancelada_por="Turista", motivo="Cambio de planes")
    )

    async def cuatro() -> bool:
        return len(await mensajes(buzon)) >= 4

    await esperar(cuatro)
    await asyncio.sleep(1)  # por si llegara un duplicado
    recibidos = {m["Subject"]: m for m in await mensajes(buzon)}
    assert set(recibidos) == {
        "Booking confirmed: Blue Pool",
        "Your request was not accepted: Blue Pool",
        "Nueva solicitud de reserva: Pozo Azul",  # al prestador, en español
        "Reserva cancelada: Pozo Azul",  # canceló el turista: se avisa al prestador
    }
    assert recibidos["Booking confirmed: Blue Pool"]["To"][0]["Address"] == "ana@correo.test"
    assert (
        recibidos["Nueva solicitud de reserva: Pozo Azul"]["To"][0]["Address"]
        == "sierra@correo.test"
    )
    assert recibidos["Reserva cancelada: Pozo Azul"]["To"][0]["Address"] == "sierra@correo.test"
    rechazo = (
        await buzon.get(f"/message/{recibidos['Your request was not accepted: Blue Pool']['ID']}")
    ).json()
    assert "Plazo de respuesta vencido" in rechazo["Text"]
    assert "<strong>was not accepted</strong>" in rechazo["HTML"]
