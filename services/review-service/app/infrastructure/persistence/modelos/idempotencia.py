"""Modelo ORM de la tabla `idempotencia` (esquema en la migración 0001)."""

from datetime import datetime

from sqlalchemy import LargeBinary, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class IdempotenciaModelo(Base):
    __tablename__ = "idempotencia"

    clave: Mapped[str] = mapped_column(Text, primary_key=True)
    estado_http: Mapped[int | None]
    cuerpo: Mapped[bytes | None] = mapped_column(LargeBinary)
    cabeceras: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    expira_en: Mapped[datetime]
