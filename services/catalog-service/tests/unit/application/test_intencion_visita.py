"""Intención de visita con dobles: una por visitante y día, Valkey caído, servicio inexistente,
hash con sal diaria y rango de fechas."""

from datetime import date, datetime
from uuid import UUID, uuid4

import pytest

from app.application.dto.intenciones_zona_dia import IntencionesZonaDia
from app.application.dto.rango_fechas import RangoFechas
from app.application.use_cases.registrar_intencion_visita import RegistrarIntencionVisita
from app.domain.errors import DatoInvalido, NoEncontrado
from app.infrastructure.cache.deduplicador_visitas_valkey import DeduplicadorVisitasValkey

HOY = date(2026, 10, 24)
IP = "190.24.1.7"


class RelojFijo:
    def ahora(self) -> datetime:
        raise NotImplementedError

    def hoy(self) -> date:
        return HOY


class DeduplicadorFalso:
    def __init__(self, caido: bool = False) -> None:
        self.vistos: set[tuple[str, UUID, date]] = set()
        self.caido = caido

    async def primera_vez(self, ip: str, servicio_id: UUID, fecha: date) -> bool | None:
        if self.caido:
            return None
        clave = (ip, servicio_id, fecha)
        nueva = clave not in self.vistos
        self.vistos.add(clave)
        return nueva

    async def olvidar(self, ip: str, servicio_id: UUID, fecha: date) -> None:
        self.vistos.discard((ip, servicio_id, fecha))


class ContadorFalso:
    def __init__(self, existentes: set[UUID]) -> None:
        self.existentes = existentes
        self.conteos: dict[UUID, int] = {}

    async def sumar(self, servicio_id: UUID, fecha: date) -> bool:
        if servicio_id not in self.existentes:
            return False
        self.conteos[servicio_id] = self.conteos.get(servicio_id, 0) + 1
        return True

    async def por_zona(self, rango: RangoFechas, zona: str | None) -> list[IntencionesZonaDia]:
        return []


SERVICIO = uuid4()


def caso(deduplicador: DeduplicadorFalso, contador: ContadorFalso) -> RegistrarIntencionVisita:
    return RegistrarIntencionVisita(deduplicador, contador, RelojFijo())


async def test_cuenta_una_vez_por_visitante_y_dia() -> None:
    deduplicador, contador = DeduplicadorFalso(), ContadorFalso({SERVICIO})
    registrar = caso(deduplicador, contador)
    await registrar.execute(SERVICIO, IP)
    await registrar.execute(SERVICIO, IP)  # el mismo turista vuelve a pedir la ruta
    await registrar.execute(SERVICIO, "181.50.3.9")  # otro visitante
    assert contador.conteos[SERVICIO] == 2


async def test_con_valkey_caido_o_sin_ip_cuenta_igual() -> None:
    contador = ContadorFalso({SERVICIO})
    await caso(DeduplicadorFalso(caido=True), contador).execute(SERVICIO, IP)
    await caso(DeduplicadorFalso(), contador).execute(SERVICIO, None)
    assert contador.conteos[SERVICIO] == 2


async def test_servicio_inexistente_es_404_y_no_deja_marca() -> None:
    deduplicador = DeduplicadorFalso()
    with pytest.raises(NoEncontrado):
        await caso(deduplicador, ContadorFalso(set())).execute(SERVICIO, IP)
    assert deduplicador.vistos == set()


def test_el_hash_cambia_cada_dia_y_no_contiene_el_ip() -> None:
    deduplicador = DeduplicadorVisitasValkey(None, "secreto")  # type: ignore[arg-type]
    hoy = deduplicador._clave(IP, SERVICIO, HOY)
    manana = deduplicador._clave(IP, SERVICIO, date(2026, 10, 25))
    otro = deduplicador._clave("181.50.3.9", SERVICIO, HOY)
    assert IP not in hoy
    assert hoy.split(":")[-1] != manana.split(":")[-1]  # no se sigue al visitante entre días
    assert hoy != otro and hoy == deduplicador._clave(IP, SERVICIO, HOY)
    otro_secreto = DeduplicadorVisitasValkey(None, "otro")  # type: ignore[arg-type]
    assert otro_secreto._clave(IP, SERVICIO, HOY) != hoy


@pytest.mark.parametrize(
    ("desde", "hasta", "regla"),
    [
        (date(2026, 10, 5), date(2026, 10, 1), "mayor_que"),
        (date(2025, 1, 1), date(2026, 3, 1), "plazo_maximo"),
    ],
)
def test_rango_de_fechas(desde: date, hasta: date, regla: str) -> None:
    with pytest.raises(DatoInvalido, match=regla):
        RangoFechas(desde, hasta)
    assert RangoFechas(date(2026, 10, 1), date(2026, 10, 31)).dias == 31
