import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RecomendacionLogModelo(Base):
    """Mapea la tabla que crea db/01-recomendacion-log.sql; el script es la fuente de verdad."""

    __tablename__ = "recomendacion_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    conversacion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    turista_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    servicio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    justificacion: Mapped[str] = mapped_column(Text)
    herramientas_usadas: Mapped[list[str]] = mapped_column(JSONB)
    modelo: Mapped[str] = mapped_column(Text)
    fecha_generacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
