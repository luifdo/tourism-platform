"""Modelo ORM de la tabla `resena` (esquema en la migración 0001)."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class ResenaModelo(Base):
    __tablename__ = "resena"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    servicio_id: Mapped[UUID]
    turista_id: Mapped[UUID]
    puntuacion: Mapped[int] = mapped_column(SmallInteger)
    aspectos: Mapped[dict[str, int]] = mapped_column(JSONB)
    comentario: Mapped[str | None] = mapped_column(Text)
    respuesta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ultima_visita: Mapped[date]
    estado: Mapped[str] = mapped_column(Text)
    reportes_pendientes: Mapped[int]
    creada_en: Mapped[datetime]
    editada_en: Mapped[datetime | None]
    version: Mapped[int]
