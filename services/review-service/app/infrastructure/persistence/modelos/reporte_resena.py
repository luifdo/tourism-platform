"""Modelo ORM de la tabla `reporte_resena` (esquema en la migración 0001)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class ReporteResenaModelo(Base):
    __tablename__ = "reporte_resena"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    resena_id: Mapped[UUID] = mapped_column(ForeignKey("resena.id", ondelete="CASCADE"))
    usuario_id: Mapped[UUID]
    rol: Mapped[str] = mapped_column(Text)
    motivo: Mapped[str] = mapped_column(Text)
    detalle: Mapped[str | None] = mapped_column(Text)
    es_dueno: Mapped[bool]
    reportado_en: Mapped[datetime]
    resuelto_en: Mapped[datetime | None]
