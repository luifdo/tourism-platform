"""Modelo ORM de la tabla `servicio_dueno` (esquema en la migración 0001)."""

from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class ServicioDuenoModelo(Base):
    __tablename__ = "servicio_dueno"

    servicio_id: Mapped[UUID] = mapped_column(primary_key=True)
    prestador_usuario_id: Mapped[UUID]
    version: Mapped[int]
