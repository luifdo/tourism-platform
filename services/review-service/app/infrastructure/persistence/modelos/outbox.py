"""Modelo ORM de la tabla `outbox` (esquema en la migración 0001)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class OutboxModelo(Base):
    __tablename__ = "outbox"

    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(Text)
    sobre: Mapped[dict[str, Any]] = mapped_column(JSONB)
    creado_en: Mapped[datetime]
    publicado_en: Mapped[datetime | None]
    intentos: Mapped[int]
