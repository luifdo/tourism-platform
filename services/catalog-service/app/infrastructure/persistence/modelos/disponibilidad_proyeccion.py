"""Modelo ORM de la tabla `disponibilidad_proyeccion` (esquema en la migración 0008)."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class DisponibilidadProyeccionModelo(Base):
    __tablename__ = "disponibilidad_proyeccion"

    servicio_id: Mapped[UUID] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(primary_key=True)
    cupos_totales: Mapped[int]
    cupos_disponibles: Mapped[int]
    version: Mapped[int]
    actualizado_en: Mapped[datetime] = mapped_column(server_default=func.now())
