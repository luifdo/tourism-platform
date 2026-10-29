"""Modelo ORM de la tabla `calificacion_resena` (esquema en las migraciones 0001 y 0006)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class CalificacionResenaModelo(Base):
    __tablename__ = "calificacion_resena"

    resena_id: Mapped[UUID] = mapped_column(primary_key=True)
    servicio_id: Mapped[UUID]
    puntuacion: Mapped[int] = mapped_column(SmallInteger)
    visible: Mapped[bool]
    ultimo_evento_en: Mapped[datetime | None]
    actualizado_en: Mapped[datetime] = mapped_column(server_default=func.now())
