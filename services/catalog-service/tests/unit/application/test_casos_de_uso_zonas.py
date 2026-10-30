"""Administración de zonas con dobles de la unidad de trabajo: roles, reasignación y auditoría."""

from datetime import UTC, date, datetime
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

import pytest

from app.application.use_cases.crear_zona import CrearZona
from app.application.use_cases.desactivar_zona import DesactivarZona
from app.application.use_cases.editar_zona import EditarZona
from app.application.use_cases.escritura_zona import EscrituraZona
from app.application.use_cases.obtener_zona import ObtenerZona
from app.domain.entities.zona import Zona
from app.domain.errors import NoEncontrado, RolNoPermitido, ZonaEnUso
from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.domain.events.evento_dominio import EventoDominio
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.geo import PoligonoGeoJSON
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.texto_traducido import TextoTraducido

AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
ENTIDAD = Identidad(uuid4(), Rol.ENTIDAD)


def poligono(desplazamiento: float = 0.0) -> PoligonoGeoJSON:
    x = -74.2 + desplazamiento
    anillo = [[x, 11.1], [x + 0.1, 11.1], [x + 0.1, 11.2], [x, 11.2], [x, 11.1]]
    return PoligonoGeoJSON.desde_geojson({"type": "Polygon", "coordinates": [anillo]})


class RelojFijo:
    def ahora(self) -> datetime:
        return AHORA

    def hoy(self) -> date:
        return AHORA.date()


class ZonasFalsas:
    def __init__(self) -> None:
        self.datos: dict[UUID, Zona] = {}
        self.reasignadas: list[UUID] = []

    async def obtener(self, zona_id: UUID) -> Zona | None:
        return self.datos.get(zona_id)

    async def guardar(self, zona: Zona) -> None:
        self.datos[zona.id] = zona

    async def reasignar_servicios(self, zona_id: UUID) -> None:
        self.reasignadas.append(zona_id)


class AlertasFalsas:
    def __init__(self) -> None:
        self.vigentes = 0

    async def contar_vigentes_de_zona(self, zona_id: UUID, ahora: datetime) -> int:
        assert ahora == AHORA
        return self.vigentes


class OutboxFalso:
    def __init__(self) -> None:
        self.eventos: list[EventoDominio] = []

    async def agregar(self, evento: EventoDominio) -> None:
        self.eventos.append(evento)


class UnidadFalsa:
    def __init__(self) -> None:
        self.zonas = ZonasFalsas()
        self.alertas = AlertasFalsas()
        self.outbox = OutboxFalso()
        self.confirmaciones = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def confirmar(self) -> None:
        self.confirmaciones += 1


class InvalidadorFalso:
    def __init__(self) -> None:
        self.llamadas = 0

    async def invalidar(self) -> None:
        self.llamadas += 1


class ConsultaFalsa:
    def __init__(self, zona: Zona | None) -> None:
        self._zona = zona

    async def zona(self, zona_id: UUID) -> Zona | None:
        return self._zona if self._zona and self._zona.id == zona_id else None


@pytest.fixture
def uow() -> UnidadFalsa:
    return UnidadFalsa()


@pytest.fixture
def invalidador() -> InvalidadorFalso:
    return InvalidadorFalso()


def casos(uow: UnidadFalsa, invalidador: InvalidadorFalso) -> tuple:
    escritura = EscrituraZona(invalidador)
    reloj = RelojFijo()
    return (
        CrearZona(lambda: uow, escritura, reloj),
        EditarZona(lambda: uow, escritura, reloj),
        DesactivarZona(lambda: uow, escritura, reloj),
    )


def existente(uow: UnidadFalsa) -> Zona:
    zona = Zona.crear(CodigoZona("prueba-minca"), TextoTraducido(es="Minca"), poligono())
    uow.zonas.datos[zona.id] = zona
    return zona


def auditoria(uow: UnidadFalsa) -> AuditoriaRegistrada:
    [evento] = uow.outbox.eventos
    assert isinstance(evento, AuditoriaRegistrada)
    return evento


@pytest.mark.parametrize("rol", [Rol.TURISTA, Rol.PRESTADOR])
async def test_solo_entidad_y_admin(
    uow: UnidadFalsa, invalidador: InvalidadorFalso, rol: Rol
) -> None:
    crear, editar, desactivar = casos(uow, invalidador)
    otro = Identidad(uuid4(), rol)
    with pytest.raises(RolNoPermitido):
        await crear.execute(otro, CodigoZona("prueba-x"), TextoTraducido(es="X"), poligono())
    with pytest.raises(RolNoPermitido):
        await desactivar.execute(otro, uuid4(), 1)
    with pytest.raises(RolNoPermitido):
        await ObtenerZona(ConsultaFalsa(None)).execute(otro, uuid4())
    assert uow.confirmaciones == 0 and not uow.outbox.eventos


async def test_crear_reasigna_audita_e_invalida(
    uow: UnidadFalsa, invalidador: InvalidadorFalso
) -> None:
    crear, _, _ = casos(uow, invalidador)
    admin = Identidad(uuid4(), Rol.ADMIN)
    zona = await crear.execute(
        admin, CodigoZona("prueba-minca"), TextoTraducido(es="Minca"), poligono()
    )
    assert uow.zonas.datos[zona.id] is zona and uow.zonas.reasignadas == [zona.id]
    evento = auditoria(uow)
    assert evento.payload() == {
        "usuario_id": str(admin.usuario_id),
        "accion": "ZONA_CREADA",
        "resultado": "EXITO",
        "detalles": {"zona_id": str(zona.id), "codigo": "prueba-minca", "version": 1},
    }
    assert evento.ocurrido_en == AHORA
    assert (uow.confirmaciones, invalidador.llamadas) == (1, 1)


async def test_editar_sin_cambiar_poligono_no_reasigna(
    uow: UnidadFalsa, invalidador: InvalidadorFalso
) -> None:
    _, editar, _ = casos(uow, invalidador)
    zona = existente(uow)
    await editar.execute(
        ENTIDAD, zona.id, 1, zona.codigo, TextoTraducido(es="Minca", en="Minca"), poligono()
    )
    assert uow.zonas.reasignadas == [] and zona.version == 2
    assert auditoria(uow).detalles["poligono_cambiado"] is False


async def test_editar_poligono_reasigna(uow: UnidadFalsa, invalidador: InvalidadorFalso) -> None:
    _, editar, _ = casos(uow, invalidador)
    zona = existente(uow)
    await editar.execute(ENTIDAD, zona.id, 1, zona.codigo, zona.nombre, poligono(0.05))
    assert uow.zonas.reasignadas == [zona.id]
    assert auditoria(uow).detalles == {
        "zona_id": str(zona.id),
        "codigo": "prueba-minca",
        "version": 2,
        "poligono_cambiado": True,
    }


async def test_editar_inexistente(uow: UnidadFalsa, invalidador: InvalidadorFalso) -> None:
    _, editar, _ = casos(uow, invalidador)
    with pytest.raises(NoEncontrado):
        await editar.execute(
            ENTIDAD, uuid4(), 1, CodigoZona("x-y"), TextoTraducido(es="X"), poligono()
        )


async def test_desactivar_reasigna_y_audita(
    uow: UnidadFalsa, invalidador: InvalidadorFalso
) -> None:
    _, _, desactivar = casos(uow, invalidador)
    zona = existente(uow)
    await desactivar.execute(ENTIDAD, zona.id, 1)
    assert not zona.activa and uow.zonas.reasignadas == [zona.id]
    assert auditoria(uow).accion == "ZONA_DESACTIVADA"
    assert invalidador.llamadas == 1


async def test_desactivar_repetido_no_hace_nada(
    uow: UnidadFalsa, invalidador: InvalidadorFalso
) -> None:
    _, _, desactivar = casos(uow, invalidador)
    zona = existente(uow)
    zona.desactivar(1, alertas_vigentes=0)
    resultado = await desactivar.execute(ENTIDAD, zona.id, 2)
    assert resultado.version == 2 and not uow.outbox.eventos
    assert (uow.confirmaciones, invalidador.llamadas, uow.zonas.reasignadas) == (0, 0, [])


async def test_desactivar_con_alertas_vigentes(
    uow: UnidadFalsa, invalidador: InvalidadorFalso
) -> None:
    _, _, desactivar = casos(uow, invalidador)
    zona = existente(uow)
    uow.alertas.vigentes = 2
    with pytest.raises(ZonaEnUso):
        await desactivar.execute(ENTIDAD, zona.id, 1)
    assert zona.activa and uow.confirmaciones == 0


async def test_obtener_zona() -> None:
    zona = Zona.crear(CodigoZona("prueba-minca"), TextoTraducido(es="Minca"), poligono())
    assert await ObtenerZona(ConsultaFalsa(zona)).execute(ENTIDAD, zona.id) is zona
    with pytest.raises(NoEncontrado):
        await ObtenerZona(ConsultaFalsa(zona)).execute(ENTIDAD, uuid4())
