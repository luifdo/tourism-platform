"""Modelo ORM de la tabla `alerta_oficial` (esquema en la migración 0001)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class AlertaOficialModelo(Base):
    __tablename__ = "alerta_oficial"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    nivel: Mapped[str] = mapped_column(Text)
    mensaje: Mapped[dict[str, str]] = mapped_column(JSONB)
    entidad_usuario_id: Mapped[UUID]
    servicio_id: Mapped[UUID | None]
    zona_id: Mapped[UUID | None]
    fecha_expiracion: Mapped[datetime]
    creada_en: Mapped[datetime]
    activa: Mapped[bool]
    version: Mapped[int]
