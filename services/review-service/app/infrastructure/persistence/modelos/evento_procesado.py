"""Modelo ORM de la tabla `evento_procesado` (esquema en la migración 0001)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class EventoProcesadoModelo(Base):
    __tablename__ = "evento_procesado"

    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    consumidor: Mapped[str] = mapped_column(Text, primary_key=True)
    procesado_en: Mapped[datetime] = mapped_column(server_default=func.now())
