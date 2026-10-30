import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.value_objects.enums import EstadoDocumento, ResultadoAuditoria, Rol, TipoDocumento
from app.infrastructure.persistence.database import Base


def pg_enum(enum_cls: type[enum.Enum], name: str) -> ENUM:
    """Tipo enum nativo de PostgreSQL que guarda el valor ("Admin"), no el nombre del miembro.

    create_type=False: los tipos los crea y elimina la migración de forma explícita.
    """
    return ENUM(
        enum_cls,
        name=name,
        values_callable=lambda members: [m.value for m in members],
        create_type=False,
    )


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


def timestamptz_now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="email_minusculas"),
        # Ley 1581 (UC6): no se registra a nadie sin aceptar el tratamiento de datos.
        CheckConstraint("habeas_data_aceptado = true", name="habeas_data_aceptado"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    rol: Mapped[Rol] = mapped_column(pg_enum(Rol, "rol"), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    email_verificado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    habeas_data_aceptado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    habeas_data_aceptado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    creado_en: Mapped[datetime] = timestamptz_now()
    # El trigger usuario_actualizado_en lo refresca en cada UPDATE, venga o no del ORM.
    actualizado_en: Mapped[datetime] = timestamptz_now()


class DocumentoVerificacion(Base):
    __tablename__ = "documento_verificacion"

    id: Mapped[uuid.UUID] = uuid_pk()
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tipo_documento: Mapped[TipoDocumento] = mapped_column(
        pg_enum(TipoDocumento, "tipo_documento"), nullable=False
    )
    objeto_s3: Mapped[str] = mapped_column(String(512), nullable=False)
    estado: Mapped[EstadoDocumento] = mapped_column(
        pg_enum(EstadoDocumento, "estado_documento"),
        nullable=False,
        server_default=EstadoDocumento.PENDIENTE.value,
    )
    motivo_rechazo: Mapped[str | None] = mapped_column(Text)
    revisado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuario.id", ondelete="RESTRICT")
    )
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_subida: Mapped[datetime] = timestamptz_now()


class BitacoraAuditoria(Base):
    """Bitácora de auditoría de solo inserción (RNF-10); la inmutabilidad la imponen triggers."""

    __tablename__ = "bitacora_auditoria"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Nulo cuando la acción es anónima (p. ej. LOGIN_FAIL de un email inexistente).
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuario.id", ondelete="RESTRICT"), index=True
    )
    accion: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resultado: Mapped[ResultadoAuditoria] = mapped_column(
        pg_enum(ResultadoAuditoria, "resultado_auditoria"), nullable=False
    )
    servicio_origen: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="iam-service"
    )
    ip_origen: Mapped[str | None] = mapped_column(INET)
    detalles: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # Momento del hecho: now() en las filas propias; el occurred_at del sobre en las de otros
    # servicios (C-39).
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    # Llave de idempotencia de los eventos de otros servicios; nula en las filas propias (C-04).
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100))  # C-05
