"""Modelo ORM de la tabla `zona` (esquema en la migración 0001)."""

from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class ZonaModelo(Base):
    __tablename__ = "zona"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(Text, unique=True)
    nombre: Mapped[dict[str, str]] = mapped_column(JSONB)
    poligono: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=False))
    activa: Mapped[bool]
    version: Mapped[int]
