"""Modelo ORM de la tabla `atractivo_servicio` (esquema en las migraciones 0001 y 0004)."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import Computed, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class AtractivoServicioModelo(Base):
    __tablename__ = "atractivo_servicio"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    prestador_id: Mapped[UUID]
    prestador_usuario_id: Mapped[UUID]
    nombre: Mapped[dict[str, str]] = mapped_column(JSONB)
    descripcion: Mapped[dict[str, str]] = mapped_column(JSONB)
    categoria: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    lat: Mapped[float]
    lon: Mapped[float]
    ubicacion: Mapped[Any] = mapped_column(
        Geography("POINT", srid=4326, spatial_index=False),
        Computed("ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography", persisted=True),
    )
    tarifa_base: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unidad_tarifa: Mapped[str] = mapped_column(Text)
    capacidad_aforo_diario: Mapped[int]
    imagenes_urls: Mapped[list[str]] = mapped_column(ARRAY(Text))
    atributos: Mapped[dict[str, Any]] = mapped_column(JSONB)
    zona_id: Mapped[UUID | None]
    activo: Mapped[bool]
    desactivado_por_suspension: Mapped[bool]
    version: Mapped[int]
    creado_en: Mapped[datetime]
    actualizado_en: Mapped[datetime]
    # Columnas generadas: Computed solo evita que SQLAlchemy las incluya en INSERT/UPDATE;
    # su expresión real está en la migración 0001 (no se usa create_all).
    busqueda_es: Mapped[Any] = mapped_column(TSVECTOR, Computed("busqueda_es", persisted=True))
    busqueda_en: Mapped[Any] = mapped_column(TSVECTOR, Computed("busqueda_en", persisted=True))
