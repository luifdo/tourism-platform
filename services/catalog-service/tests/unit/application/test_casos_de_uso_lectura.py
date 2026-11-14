from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest

from app.application.dto.alerta_vista import AlertaVista
from app.application.dto.criterios_busqueda import CriteriosBusqueda
from app.application.dto.pagina_servicios import PaginaServicios
from app.application.dto.servicio_detalle import ServicioDetalle
from app.application.use_cases.buscar_servicios import BuscarServicios
from app.application.use_cases.listar_alertas import ListarAlertas
from app.application.use_cases.obtener_servicio import ObtenerServicio
from app.domain.errors import NoEncontrado
from app.domain.value_objects.idioma import Idioma

AHORA = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)


class RelojFijo:
    def ahora(self) -> datetime:
        return AHORA

    def hoy(self) -> date:
        return AHORA.date()


class ConsultaVacia:
    def __init__(self) -> None:
        self.recibido: dict = {}

    async def buscar(self, criterios: CriteriosBusqueda) -> PaginaServicios:
        self.recibido["criterios"] = criterios
        return PaginaServicios(items=(), pagina=criterios.pagina, tamano=criterios.tamano, total=0)

    async def detalle(self, servicio_id: UUID, ahora: datetime) -> ServicioDetalle | None:
        self.recibido["ahora"] = ahora
        return None

    async def vigentes(
        self, ahora: datetime, zona: str | None = None, servicio_id: UUID | None = None
    ) -> list[AlertaVista]:
        self.recibido |= {"ahora": ahora, "zona": zona, "servicio_id": servicio_id}
        return []


async def test_buscar_delega_los_criterios() -> None:
    consulta = ConsultaVacia()
    criterios = CriteriosBusqueda(idioma=Idioma.EN, pagina=3)
    pagina = await BuscarServicios(consulta).execute(criterios)
    assert consulta.recibido["criterios"] is criterios and pagina.pagina == 3


async def test_servicio_inexistente_o_inactivo_es_no_encontrado() -> None:
    consulta = ConsultaVacia()
    with pytest.raises(NoEncontrado):
        await ObtenerServicio(consulta, RelojFijo()).execute(uuid4())
    assert consulta.recibido["ahora"] == AHORA  # las alertas se filtran con la hora del reloj


async def test_alertas_usan_la_hora_del_reloj() -> None:
    consulta = ConsultaVacia()
    servicio_id = uuid4()
    await ListarAlertas(consulta, RelojFijo()).execute(zona="minca", servicio_id=servicio_id)
    assert consulta.recibido == {"ahora": AHORA, "zona": "minca", "servicio_id": servicio_id}
