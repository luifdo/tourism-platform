"""Cableado de casos de uso con sus adaptadores.

Los adaptadores (engine, sesiones, Valkey, consultas) se crean una vez en el lifespan de
`main.py` y viven en `app.state`; aquí solo se arman los casos de uso por petición. Las
pruebas reemplazan estas funciones con `app.dependency_overrides`.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.ports.almacen_idempotencia import AlmacenIdempotencia
from app.application.ports.almacen_imagenes import AlmacenImagenes
from app.application.ports.consulta_alertas import ConsultaAlertas
from app.application.ports.consulta_analitica import ConsultaAnalitica
from app.application.ports.consulta_capacidad import ConsultaCapacidad
from app.application.ports.consulta_mapa import ConsultaMapa
from app.application.ports.consulta_prestador import ConsultaPrestador
from app.application.ports.consulta_servicios import ConsultaServicios
from app.application.ports.consulta_zonas import ConsultaZonas
from app.application.ports.contador_intenciones import ContadorIntenciones
from app.application.ports.deduplicador_visitas import DeduplicadorVisitas
from app.application.ports.geocodificador import Geocodificador
from app.application.ports.invalidador_cache import InvalidadorCache
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.application.use_cases.buscar_servicios import BuscarServicios
from app.application.use_cases.cambiar_estado_servicio import CambiarEstadoServicio
from app.application.use_cases.check_health import CheckHealth
from app.application.use_cases.consultar_capacidad import ConsultarCapacidad
from app.application.use_cases.consultar_demanda import ConsultarDemanda
from app.application.use_cases.crear_zona import CrearZona
from app.application.use_cases.desactivar_zona import DesactivarZona
from app.application.use_cases.editar_alerta import EditarAlerta
from app.application.use_cases.editar_perfil import EditarPerfil
from app.application.use_cases.editar_servicio import EditarServicio
from app.application.use_cases.editar_zona import EditarZona
from app.application.use_cases.escritura_alerta import EscrituraAlerta
from app.application.use_cases.escritura_servicio import EscrituraServicio
from app.application.use_cases.escritura_zona import EscrituraZona
from app.application.use_cases.exportar_reporte_demanda import ExportarReporteDemanda
from app.application.use_cases.geocodificar_direccion import GeocodificarDireccion
from app.application.use_cases.listar_alertas import ListarAlertas
from app.application.use_cases.listar_alertas_entidad import ListarAlertasEntidad
from app.application.use_cases.listar_intenciones_visita import ListarIntencionesVisita
from app.application.use_cases.listar_servicios_prestador import ListarServiciosPrestador
from app.application.use_cases.listar_zonas import ListarZonas
from app.application.use_cases.obtener_metricas_prestador import ObtenerMetricasPrestador
from app.application.use_cases.obtener_perfil import ObtenerPerfil
from app.application.use_cases.obtener_servicio import ObtenerServicio
from app.application.use_cases.obtener_zona import ObtenerZona
from app.application.use_cases.publicar_alerta import PublicarAlerta
from app.application.use_cases.registrar_intencion_visita import RegistrarIntencionVisita
from app.application.use_cases.registrar_servicio import RegistrarServicio
from app.application.use_cases.retirar_alerta import RetirarAlerta
from app.application.use_cases.solicitar_subida_imagen import SolicitarSubidaImagen
from app.application.use_cases.ver_alertas_en_mapa import VerAlertasEnMapa
from app.application.use_cases.ver_mapa_calor import VerMapaCalor
from app.application.use_cases.ver_servicios_en_mapa import VerServiciosEnMapa
from app.application.use_cases.ver_tablero import VerTablero
from app.application.use_cases.ver_zonas_en_mapa import VerZonasEnMapa
from app.config import Settings, get_settings
from app.domain.ports.reloj import Reloj
from app.infrastructure.persistence.database import SqlAlchemyDatabaseProbe


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


def get_reloj(request: Request) -> Reloj:
    return request.app.state.reloj


def get_consulta_servicios(request: Request) -> ConsultaServicios:
    return request.app.state.consulta_servicios


def get_consulta_zonas(request: Request) -> ConsultaZonas:
    return request.app.state.consulta_zonas


def get_consulta_alertas(request: Request) -> ConsultaAlertas:
    return request.app.state.consulta_alertas


def get_consulta_mapa(request: Request) -> ConsultaMapa:
    return request.app.state.consulta_mapa


def get_consulta_prestador(request: Request) -> ConsultaPrestador:
    return request.app.state.consulta_prestador


def get_unidad_de_trabajo(request: Request) -> FabricaUnidadDeTrabajo:
    return request.app.state.unidad_de_trabajo


def get_invalidador_cache(request: Request) -> InvalidadorCache:
    return request.app.state.invalidador_cache


def get_almacen_imagenes(request: Request) -> AlmacenImagenes:
    return request.app.state.almacen_imagenes


def get_geocodificador(request: Request) -> Geocodificador:
    return request.app.state.geocodificador


def get_idempotencia(request: Request) -> AlmacenIdempotencia:
    return request.app.state.idempotencia


def get_check_health(
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CheckHealth:
    probe = SqlAlchemyDatabaseProbe(engine, settings.database_health_timeout_seconds)
    return CheckHealth(database=probe)


def get_buscar_servicios(
    consulta: Annotated[ConsultaServicios, Depends(get_consulta_servicios)],
) -> BuscarServicios:
    return BuscarServicios(consulta)


def get_obtener_servicio(
    consulta: Annotated[ConsultaServicios, Depends(get_consulta_servicios)],
    reloj: Annotated[Reloj, Depends(get_reloj)],
) -> ObtenerServicio:
    return ObtenerServicio(consulta, reloj)


def get_listar_zonas(
    consulta: Annotated[ConsultaZonas, Depends(get_consulta_zonas)],
) -> ListarZonas:
    return ListarZonas(consulta)


def get_listar_alertas(
    consulta: Annotated[ConsultaAlertas, Depends(get_consulta_alertas)],
    reloj: Annotated[Reloj, Depends(get_reloj)],
) -> ListarAlertas:
    return ListarAlertas(consulta, reloj)


def get_ver_servicios_en_mapa(
    consulta: Annotated[ConsultaMapa, Depends(get_consulta_mapa)],
) -> VerServiciosEnMapa:
    return VerServiciosEnMapa(consulta)


def get_ver_zonas_en_mapa(
    consulta: Annotated[ConsultaMapa, Depends(get_consulta_mapa)],
) -> VerZonasEnMapa:
    return VerZonasEnMapa(consulta)


def get_ver_alertas_en_mapa(
    consulta: Annotated[ConsultaMapa, Depends(get_consulta_mapa)],
    reloj: Annotated[Reloj, Depends(get_reloj)],
) -> VerAlertasEnMapa:
    return VerAlertasEnMapa(consulta, reloj)


Uow = Annotated[FabricaUnidadDeTrabajo, Depends(get_unidad_de_trabajo)]
Prestador = Annotated[ConsultaPrestador, Depends(get_consulta_prestador)]
Imagenes = Annotated[AlmacenImagenes, Depends(get_almacen_imagenes)]
RelojDep = Annotated[Reloj, Depends(get_reloj)]


def get_escritura_servicio(
    consulta: Prestador,
    invalidador: Annotated[InvalidadorCache, Depends(get_invalidador_cache)],
) -> EscrituraServicio:
    return EscrituraServicio(consulta, invalidador)


Escritura = Annotated[EscrituraServicio, Depends(get_escritura_servicio)]


def get_obtener_perfil(consulta: Prestador) -> ObtenerPerfil:
    return ObtenerPerfil(consulta)


def get_editar_perfil(uow: Uow) -> EditarPerfil:
    return EditarPerfil(uow)


def get_registrar_servicio(
    uow: Uow, escritura: Escritura, imagenes: Imagenes, reloj: RelojDep
) -> RegistrarServicio:
    return RegistrarServicio(uow, escritura, imagenes, reloj)


def get_editar_servicio(
    uow: Uow, escritura: Escritura, imagenes: Imagenes, reloj: RelojDep
) -> EditarServicio:
    return EditarServicio(uow, escritura, imagenes, reloj)


def get_cambiar_estado_servicio(
    uow: Uow, escritura: Escritura, reloj: RelojDep
) -> CambiarEstadoServicio:
    return CambiarEstadoServicio(uow, escritura, reloj)


def get_listar_servicios_prestador(consulta: Prestador) -> ListarServiciosPrestador:
    return ListarServiciosPrestador(consulta)


def get_solicitar_subida_imagen(consulta: Prestador, imagenes: Imagenes) -> SolicitarSubidaImagen:
    return SolicitarSubidaImagen(consulta, imagenes)


def get_geocodificar(
    geocodificador: Annotated[Geocodificador, Depends(get_geocodificador)],
) -> GeocodificarDireccion:
    return GeocodificarDireccion(geocodificador)


def get_escritura_zona(
    invalidador: Annotated[InvalidadorCache, Depends(get_invalidador_cache)],
) -> EscrituraZona:
    return EscrituraZona(invalidador)


EscrituraZonaDep = Annotated[EscrituraZona, Depends(get_escritura_zona)]


def get_crear_zona(uow: Uow, escritura: EscrituraZonaDep, reloj: RelojDep) -> CrearZona:
    return CrearZona(uow, escritura, reloj)


def get_obtener_zona(
    consulta: Annotated[ConsultaZonas, Depends(get_consulta_zonas)],
) -> ObtenerZona:
    return ObtenerZona(consulta)


def get_editar_zona(uow: Uow, escritura: EscrituraZonaDep, reloj: RelojDep) -> EditarZona:
    return EditarZona(uow, escritura, reloj)


def get_desactivar_zona(uow: Uow, escritura: EscrituraZonaDep, reloj: RelojDep) -> DesactivarZona:
    return DesactivarZona(uow, escritura, reloj)


def get_publicar_alerta(uow: Uow, reloj: RelojDep) -> PublicarAlerta:
    return PublicarAlerta(uow, EscrituraAlerta(), reloj)


def get_editar_alerta(uow: Uow, reloj: RelojDep) -> EditarAlerta:
    return EditarAlerta(uow, EscrituraAlerta(), reloj)


def get_retirar_alerta(uow: Uow, reloj: RelojDep) -> RetirarAlerta:
    return RetirarAlerta(uow, EscrituraAlerta(), reloj)


def get_listar_alertas_entidad(
    consulta: Annotated[ConsultaAlertas, Depends(get_consulta_alertas)], reloj: RelojDep
) -> ListarAlertasEntidad:
    return ListarAlertasEntidad(consulta, reloj)


def get_consulta_capacidad(request: Request) -> ConsultaCapacidad:
    return request.app.state.consulta_capacidad


def get_consultar_capacidad(
    consulta: Annotated[ConsultaCapacidad, Depends(get_consulta_capacidad)], reloj: RelojDep
) -> ConsultarCapacidad:
    return ConsultarCapacidad(consulta, reloj)


def get_ver_mapa_calor(
    mapa: Annotated[ConsultaMapa, Depends(get_consulta_mapa)],
    capacidad: Annotated[ConsultarCapacidad, Depends(get_consultar_capacidad)],
) -> VerMapaCalor:
    return VerMapaCalor(mapa, capacidad)


def get_contador_intenciones(request: Request) -> ContadorIntenciones:
    return request.app.state.contador_intenciones


def get_deduplicador_visitas(request: Request) -> DeduplicadorVisitas:
    return request.app.state.deduplicador_visitas


Contador = Annotated[ContadorIntenciones, Depends(get_contador_intenciones)]


def get_registrar_intencion_visita(
    deduplicador: Annotated[DeduplicadorVisitas, Depends(get_deduplicador_visitas)],
    contador: Contador,
    reloj: RelojDep,
) -> RegistrarIntencionVisita:
    return RegistrarIntencionVisita(deduplicador, contador, reloj)


def get_listar_intenciones_visita(contador: Contador) -> ListarIntencionesVisita:
    return ListarIntencionesVisita(contador)


def get_consulta_analitica(request: Request) -> ConsultaAnalitica:
    return request.app.state.consulta_analitica


Analitica = Annotated[ConsultaAnalitica, Depends(get_consulta_analitica)]


def get_obtener_metricas_prestador(
    prestador: Prestador, analitica: Analitica
) -> ObtenerMetricasPrestador:
    return ObtenerMetricasPrestador(prestador, analitica)


def get_consultar_demanda(
    analitica: Analitica, zonas: Annotated[ConsultaZonas, Depends(get_consulta_zonas)]
) -> ConsultarDemanda:
    return ConsultarDemanda(analitica, zonas)


def get_ver_tablero(
    analitica: Analitica,
    capacidad: Annotated[ConsultarCapacidad, Depends(get_consultar_capacidad)],
    alertas: Annotated[ConsultaAlertas, Depends(get_consulta_alertas)],
    reloj: RelojDep,
) -> VerTablero:
    return VerTablero(analitica, capacidad, alertas, reloj)


def get_exportar_reporte_demanda(
    analitica: Analitica,
    zonas: Annotated[ConsultaZonas, Depends(get_consulta_zonas)],
    uow: Uow,
    reloj: RelojDep,
) -> ExportarReporteDemanda:
    return ExportarReporteDemanda(analitica, zonas, uow, reloj)
