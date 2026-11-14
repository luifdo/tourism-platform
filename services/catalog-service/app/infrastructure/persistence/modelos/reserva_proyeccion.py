"""Modelo ORM de la tabla `reserva_proyeccion` (esquema en la migración 0001)."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class ReservaProyeccionModelo(Base):
    __tablename__ = "reserva_proyeccion"

    reserva_id: Mapped[UUID] = mapped_column(primary_key=True)
    servicio_id: Mapped[UUID]
    prestador_id: Mapped[UUID]
    turista_id: Mapped[UUID]
    fecha_reserva: Mapped[date]
    numero_personas: Mapped[int]
    estado: Mapped[str] = mapped_column(Text)
    ultimo_evento_en: Mapped[datetime]
