"""prestador.aprobado / prestador.suspendido con dobles: perfil, servicios, orden e idempotencia."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

import pytest

from app.application.dto.prestador_aprobado_recibido import PrestadorAprobadoRecibido
from app.application.dto.prestador_suspendido_recibido import PrestadorSuspendidoRecibido
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.aplicar_prestador_aprobado import AplicarPrestadorAprobado
from app.application.use_cases.aplicar_prestador_suspendido import AplicarPrestadorSuspendido
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.events.evento_dominio import EventoDominio
from app.domain.events.servicio_publicado import ServicioPublicado
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio

AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
PRESTADOR, USUARIO = uuid4(), uuid4()


class RelojFijo:
    def ahora(self) -> datetime:
        return AHORA

    def hoy(self) -> date:
        return AHORA.date()


class Prestadores:
    def __init__(self) -> None:
        self.datos: dict[UUID, PrestadorPerfil] = {}

    async def obtener(self, prestador_id: UUID) -> PrestadorPerfil | None:
        return self.datos.get(prestador_id)

    async def guardar(self, perfil: PrestadorPerfil) -> None:
        self.datos[perfil.id] = perfil


class Servicios:
    def __init__(self) -> None:
        self.datos: list[AtractivoServicio] = []

    async def listar_por_prestador(self, prestador_id: UUID) -> list[AtractivoServicio]:
        return [s for s in self.datos if s.prestador_id == prestador_id]

    async def guardar(self, servicio: AtractivoServicio) -> None:
        pass


class Procesados:
    def __init__(self) -> None:
        self.ids: set[UUID] = set()

    async def registrar(self, event_id: UUID, consumidor: str) -> bool:
        if event_id in self.ids:
            return False
        self.ids.add(event_id)
        return True


class Outbox:
    def __init__(self) -> None:
        self.eventos: list[EventoDominio] = []

    async def agregar(self, evento: EventoDominio) -> None:
        self.eventos.append(evento)


class Unidad:
    def __init__(self) -> None:
        self.prestadores, self.servicios = Prestadores(), Servicios()
        self.eventos_procesados, self.outbox = Procesados(), Outbox()
        self.confirmaciones = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, t: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None
    ) -> None:
        return None

    async def confirmar(self) -> None:
        self.confirmaciones += 1


class Invalidador:
    def __init__(self) -> None:
        self.llamadas = 0

    async def invalidar(self) -> None:
        self.llamadas += 1


@pytest.fixture
def uow() -> Unidad:
    return Unidad()


@pytest.fixture
def invalidador() -> Invalidador:
    return Invalidador()


def aprobado(minutos: int = 0, razon: str | None = "Minca Viva") -> PrestadorAprobadoRecibido:
    return PrestadorAprobadoRecibido(
        uuid4(), AHORA + timedelta(minutes=minutos), PRESTADOR, USUARIO, razon
    )


def suspendido(minutos: int = 0) -> PrestadorSuspendidoRecibido:
    return PrestadorSuspendidoRecibido(
        uuid4(), AHORA + timedelta(minutes=minutos), PRESTADOR, USUARIO
    )


def casos(uow: Unidad, invalidador: Invalidador) -> tuple:
    return (
        AplicarPrestadorAprobado(lambda: uow, invalidador, RelojFijo()),
        AplicarPrestadorSuspendido(lambda: uow, invalidador, RelojFijo()),
    )


def servicio_de(perfil: PrestadorPerfil) -> AtractivoServicio:
    datos = DatosServicio(
        nombre=TextoTraducido(es="Pozo Azul"),
        descripcion=TextoTraducido(es="Entrada"),
        tipo=TipoServicio.RESERVA_PARQUE,
        ubicacion=Coordenada(lat=11.14, lon=-74.11),
        tarifa_base=Tarifa(Decimal("10000")),
        unidad_tarifa=UnidadTarifa.POR_PERSONA,
        capacidad_aforo_diario=50,
        atributos=AtributosServicio(entrada=BloqueEntrada()),
    )
    return AtractivoServicio.registrar(perfil, datos, "https://s3/", AHORA)


async def test_aprobado_crea_el_perfil_y_un_duplicado_se_descarta(
    uow: Unidad, invalidador: Invalidador
) -> None:
    aprobar, _ = casos(uow, invalidador)
    evento = aprobado()
    assert await aprobar.execute(evento) is ResultadoConsumo.APLICADO
    perfil = uow.prestadores.datos[PRESTADOR]
    assert (perfil.usuario_id, perfil.razon_social, perfil.activo) == (USUARIO, "Minca Viva", True)
    assert perfil.estado_iam_en == evento.ocurrido_en
    assert await aprobar.execute(evento) is ResultadoConsumo.DUPLICADO
    assert invalidador.llamadas == 0  # sin servicios, nada que invalidar


async def test_suspender_apaga_servicios_y_reaprobar_restaura_solo_esos(
    uow: Unidad, invalidador: Invalidador
) -> None:
    aprobar, suspender = casos(uow, invalidador)
    await aprobar.execute(aprobado(0))
    perfil = uow.prestadores.datos[PRESTADOR]
    activo, apagado_por_el = servicio_de(perfil), servicio_de(perfil)
    apagado_por_el.desactivar(perfil, 1, AHORA)
    uow.servicios.datos = [activo, apagado_por_el]

    assert await suspender.execute(suspendido(1)) is ResultadoConsumo.APLICADO
    assert not perfil.activo and not activo.activo and activo.desactivado_por_suspension
    [evento] = uow.outbox.eventos
    assert isinstance(evento, ServicioPublicado) and evento.payload()["activo"] is False
    assert invalidador.llamadas == 1

    assert await aprobar.execute(aprobado(2)) is ResultadoConsumo.APLICADO
    assert perfil.activo and activo.activo
    assert not apagado_por_el.activo  # lo apagó el prestador: sigue apagado
    assert len(uow.outbox.eventos) == 2 and invalidador.llamadas == 2


async def test_un_aprobado_viejo_no_reactiva_a_un_suspendido(
    uow: Unidad, invalidador: Invalidador
) -> None:
    aprobar, suspender = casos(uow, invalidador)
    await aprobar.execute(aprobado(0))
    await suspender.execute(suspendido(10))
    # Un reintento trae tarde una aprobación anterior a la suspensión.
    assert await aprobar.execute(aprobado(5)) is ResultadoConsumo.IGNORADO
    assert not uow.prestadores.datos[PRESTADOR].activo


async def test_suspendido_antes_de_su_aprobacion_no_deja_activo_al_prestador(
    uow: Unidad, invalidador: Invalidador
) -> None:
    aprobar, suspender = casos(uow, invalidador)
    # iam lo aprobó (minuto 0) y lo suspendió (minuto 5); por un reintento llega primero la
    # suspensión.
    assert await suspender.execute(suspendido(5)) is ResultadoConsumo.APLICADO
    perfil = uow.prestadores.datos[PRESTADOR]
    assert not perfil.activo and perfil.estado_iam_en == AHORA + timedelta(minutes=5)
    assert await aprobar.execute(aprobado(0)) is ResultadoConsumo.IGNORADO
    assert not uow.prestadores.datos[PRESTADOR].activo

    # Una aprobación nueva (iam lo vuelve a habilitar) sí lo activa, con su razón social.
    assert await aprobar.execute(aprobado(10)) is ResultadoConsumo.APLICADO
    perfil = uow.prestadores.datos[PRESTADOR]
    assert perfil.activo and perfil.razon_social == "Minca Viva"


async def test_aprobado_repetido_actualiza_la_razon_social(
    uow: Unidad, invalidador: Invalidador
) -> None:
    aprobar, _ = casos(uow, invalidador)
    await aprobar.execute(aprobado(0, razon=None))
    await aprobar.execute(aprobado(1, razon="Minca Viva S.A.S."))
    assert uow.prestadores.datos[PRESTADOR].razon_social == "Minca Viva S.A.S."
