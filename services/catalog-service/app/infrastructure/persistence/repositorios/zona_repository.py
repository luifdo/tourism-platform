"""Repositorio de Zona (tabla `zona`) y asignación de zonas con PostGIS."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.zona import Zona
from app.domain.errors import CodigoExistente, DatoInvalido
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.geo import Coordenada, PoligonoGeoJSON
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.infrastructure.persistence.modelos.zona import ZonaModelo

# Zona activa que cubre un punto; si varias lo cubren, gana la de menor área (la más específica).
_ZONA_QUE_CUBRE = """
    SELECT z.id FROM zona z
    WHERE z.activa AND ST_Covers(z.poligono, {punto})
    ORDER BY ST_Area(z.poligono) ASC
    LIMIT 1
"""

# SQLSTATE de PostgreSQL: llave única repetida (`codigo`) y CHECK incumplido (`ST_IsValid`).
_UNICO_VIOLADO = "23505"
_CHECK_VIOLADO = "23514"


def columnas_zona() -> tuple[Any, Any]:
    """Modelo y polígono en GeoJSON (15 decimales: sin perder precisión al reeditar)."""
    return ZonaModelo, func.ST_AsGeoJSON(ZonaModelo.poligono, 15)


def zona_desde_fila(modelo: ZonaModelo, geojson: str) -> Zona:
    return Zona(
        id=modelo.id,
        codigo=CodigoZona(modelo.codigo),
        nombre=TextoTraducido(**modelo.nombre),
        poligono=PoligonoGeoJSON.desde_geojson(json.loads(geojson)),
        activa=modelo.activa,
        version=modelo.version,
    )


class SqlZonaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener(self, zona_id: UUID) -> Zona | None:
        return await self._uno(ZonaModelo.id == zona_id)

    async def obtener_por_codigo(self, codigo: CodigoZona) -> Zona | None:
        return await self._uno(ZonaModelo.codigo == codigo.valor)

    async def zona_de(self, punto: Coordenada) -> UUID | None:
        consulta = _ZONA_QUE_CUBRE.format(punto="ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)")
        return await self._session.scalar(text(consulta), {"lon": punto.lon, "lat": punto.lat})

    async def reasignar_servicios(self, zona_id: UUID) -> None:
        """Recalcula la zona de los servicios que estaban en ella o que su polígono cubre ahora."""
        consulta = _ZONA_QUE_CUBRE.format(punto="s.ubicacion::geometry")
        await self._session.execute(
            text(
                f"""
                UPDATE atractivo_servicio s
                SET zona_id = ({consulta})
                WHERE s.zona_id = :zona_id
                   OR ST_Covers((SELECT poligono FROM zona WHERE id = :zona_id),
                                s.ubicacion::geometry)
                """
            ),
            {"zona_id": zona_id},
        )

    async def guardar(self, zona: Zona) -> None:
        """Traduce las restricciones de la tabla a errores del dominio.

        El código único y la validez del polígono los garantiza PostgreSQL, así dos
        peticiones simultáneas con el mismo código no pasan las dos.
        """
        sentencia = insert(ZonaModelo).values(
            id=zona.id,
            codigo=zona.codigo.valor,
            nombre=zona.nombre.a_dict(),
            poligono=func.ST_Multi(
                func.ST_SetSRID(
                    func.ST_GeomFromGeoJSON(json.dumps(zona.poligono.a_geojson())), 4326
                )
            ),
            activa=zona.activa,
            version=zona.version,
        )
        columnas = ("codigo", "nombre", "poligono", "activa", "version")
        try:
            await self._session.execute(
                sentencia.on_conflict_do_update(
                    index_elements=["id"], set_={c: sentencia.excluded[c] for c in columnas}
                )
            )
        except IntegrityError as exc:
            estado = getattr(exc.orig, "sqlstate", None)
            if estado == _UNICO_VIOLADO:
                raise CodigoExistente(codigo=zona.codigo.valor) from exc
            if estado == _CHECK_VIOLADO:
                raise DatoInvalido(campo="poligono", regla="poligono_invalido") from exc
            raise

    async def _uno(self, condicion: Any) -> Zona | None:
        resultado = await self._session.execute(
            select(*columnas_zona()).where(condicion).with_for_update()
        )
        fila = resultado.first()
        return zona_desde_fila(*fila) if fila else None
