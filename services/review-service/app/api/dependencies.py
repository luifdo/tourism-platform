"""Cableado de casos de uso con sus adaptadores.

Los adaptadores (engine, sesiones, idempotencia) se crean una vez en el lifespan de
`main.py` y viven en `app.state`; aquí solo se arman los casos de uso por petición. Las
pruebas reemplazan estas funciones con `app.dependency_overrides`.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.ports.almacen_idempotencia import AlmacenIdempotencia
from app.application.ports.consulta_resenas import ConsultaResenas
from app.application.use_cases.check_health import CheckHealth
from app.application.use_cases.editar_resena import EditarResena
from app.application.use_cases.escribir_resena import EscribirResena
from app.application.use_cases.listar_mis_resenas import ListarMisResenas
from app.application.use_cases.listar_pendientes import ListarPendientes
from app.application.use_cases.listar_resenas_prestador import ListarResenasPrestador
from app.application.use_cases.listar_resenas_servicio import ListarResenasServicio
from app.application.use_cases.obtener_resena_publica import ObtenerResenaPublica
from app.application.use_cases.responder_resena import ResponderResena
from app.application.use_cases.resumir_servicio import ResumirServicio
from app.config import Settings, get_settings
from app.domain.ports.reloj import Reloj
from app.domain.ports.unidad_de_trabajo import FabricaUnidadDeTrabajo
from app.infrastructure.persistence.database import SqlAlchemyDatabaseProbe


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


def get_reloj(request: Request) -> Reloj:
    return request.app.state.reloj


def get_unidad_de_trabajo(request: Request) -> FabricaUnidadDeTrabajo:
    return request.app.state.unidad_de_trabajo


def get_idempotencia(request: Request) -> AlmacenIdempotencia:
    return request.app.state.idempotencia


def get_consulta_resenas(request: Request) -> ConsultaResenas:
    return request.app.state.consulta_resenas


UowDep = Annotated[FabricaUnidadDeTrabajo, Depends(get_unidad_de_trabajo)]
RelojDep = Annotated[Reloj, Depends(get_reloj)]
ConsultaDep = Annotated[ConsultaResenas, Depends(get_consulta_resenas)]


def get_check_health(
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CheckHealth:
    probe = SqlAlchemyDatabaseProbe(engine, settings.database_health_timeout_seconds)
    return CheckHealth(database=probe)


def get_escribir_resena(uow: UowDep, reloj: RelojDep) -> EscribirResena:
    return EscribirResena(uow, reloj)


def get_editar_resena(uow: UowDep, reloj: RelojDep) -> EditarResena:
    return EditarResena(uow, reloj)


def get_listar_resenas_servicio(consulta: ConsultaDep) -> ListarResenasServicio:
    return ListarResenasServicio(consulta)


def get_resumir_servicio(consulta: ConsultaDep) -> ResumirServicio:
    return ResumirServicio(consulta)


def get_obtener_resena_publica(consulta: ConsultaDep) -> ObtenerResenaPublica:
    return ObtenerResenaPublica(consulta)


def get_listar_mis_resenas(consulta: ConsultaDep) -> ListarMisResenas:
    return ListarMisResenas(consulta)


def get_listar_pendientes(consulta: ConsultaDep) -> ListarPendientes:
    return ListarPendientes(consulta)


def get_listar_resenas_prestador(consulta: ConsultaDep) -> ListarResenasPrestador:
    return ListarResenasPrestador(consulta)


def get_responder_resena(uow: UowDep, reloj: RelojDep) -> ResponderResena:
    return ResponderResena(uow, reloj)
