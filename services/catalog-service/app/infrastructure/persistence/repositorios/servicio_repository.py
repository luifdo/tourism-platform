"""Repositorio de AtractivoServicio (tabla `atractivo_servicio`)."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.persistence.modelos.atractivo_servicio import AtractivoServicioModelo
from app.infrastructure.persistence.repositorios.comun import upsert


def servicio_desde_modelo(fila: AtractivoServicioModelo) -> AtractivoServicio:
    """También lo usan las consultas de lectura, que leen sin bloquear filas."""
    return AtractivoServicio(
        id=fila.id,
        prestador_id=fila.prestador_id,
        prestador_usuario_id=fila.prestador_usuario_id,
        datos=DatosServicio(
            nombre=TextoTraducido(**fila.nombre),
            descripcion=TextoTraducido(**fila.descripcion),
            tipo=TipoServicio(fila.tipo),
            ubicacion=Coordenada(lat=fila.lat, lon=fila.lon),
            tarifa_base=Tarifa(Decimal(fila.tarifa_base)),
            unidad_tarifa=UnidadTarifa(fila.unidad_tarifa),
            capacidad_aforo_diario=fila.capacidad_aforo_diario,
            imagenes_urls=tuple(fila.imagenes_urls),
            atributos=AtributosServicio.desde_json(fila.atributos),
        ),
        creado_en=fila.creado_en,
        actualizado_en=fila.actualizado_en,
        zona_id=fila.zona_id,
        activo=fila.activo,
        desactivado_por_suspension=fila.desactivado_por_suspension,
        version=fila.version,
    )


class SqlServicioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener(self, servicio_id: UUID) -> AtractivoServicio | None:
        fila = await self._session.scalar(
            select(AtractivoServicioModelo)
            .where(AtractivoServicioModelo.id == servicio_id)
            .with_for_update()
        )
        return servicio_desde_modelo(fila) if fila else None

    async def listar_por_prestador(self, prestador_id: UUID) -> list[AtractivoServicio]:
        filas = await self._session.scalars(
            select(AtractivoServicioModelo)
            .where(AtractivoServicioModelo.prestador_id == prestador_id)
            .order_by(AtractivoServicioModelo.creado_en)
            .with_for_update()
        )
        return [servicio_desde_modelo(f) for f in filas]

    async def guardar(self, servicio: AtractivoServicio) -> None:
        datos = servicio.datos
        await upsert(
            self._session,
            AtractivoServicioModelo,
            {
                "id": servicio.id,
                "prestador_id": servicio.prestador_id,
                "prestador_usuario_id": servicio.prestador_usuario_id,
                "nombre": datos.nombre.a_dict(),
                "descripcion": datos.descripcion.a_dict(),
                "categoria": datos.categoria.value,
                "tipo": datos.tipo.value,
                "lat": datos.ubicacion.lat,
                "lon": datos.ubicacion.lon,
                "tarifa_base": datos.tarifa_base.valor,
                "unidad_tarifa": datos.unidad_tarifa.value,
                "capacidad_aforo_diario": datos.capacidad_aforo_diario,
                "imagenes_urls": list(datos.imagenes_urls),
                "atributos": datos.atributos.a_json(),
                "zona_id": servicio.zona_id,
                "activo": servicio.activo,
                "desactivado_por_suspension": servicio.desactivado_por_suspension,
                "version": servicio.version,
                "creado_en": servicio.creado_en,
                "actualizado_en": servicio.actualizado_en,
            },
        )
