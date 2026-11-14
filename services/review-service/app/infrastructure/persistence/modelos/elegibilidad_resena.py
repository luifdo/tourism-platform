"""Modelo ORM de la tabla `elegibilidad_resena` (esquema en la migración 0001)."""

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class ElegibilidadResenaModelo(Base):
    __tablename__ = "elegibilidad_resena"

    turista_id: Mapped[UUID] = mapped_column(primary_key=True)
    servicio_id: Mapped[UUID] = mapped_column(primary_key=True)
    ultima_visita: Mapped[date]
