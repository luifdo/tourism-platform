import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.usuario import Usuario
from app.domain.exceptions import UsuarioYaExisteError
from app.domain.value_objects.email import Email
from app.domain.value_objects.enums import Idioma
from app.infrastructure.persistence.models import Usuario as UsuarioModel

# Nombre fijado por la naming convention de Base y por la migración inicial.
UQ_USUARIO_EMAIL = "uq_usuario_email"


class SqlAlchemyUsuarioRepository:
    """Implementa UsuarioRepository sobre la tabla usuario."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, usuario: Usuario) -> Usuario:
        model = _to_model(usuario)
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # Dos registros simultáneos con el mismo correo pasan ambos el find_by_email;
            # la UNIQUE de PostgreSQL es la que decide.
            if UQ_USUARIO_EMAIL in str(exc.orig):
                raise UsuarioYaExisteError() from exc
            raise
        # Trae los valores que asigna la base (id, creado_en, actualizado_en).
        await self._session.refresh(model)
        return _to_entity(model)

    async def find_by_email(self, email: Email) -> Usuario | None:
        model = await self._session.scalar(
            select(UsuarioModel).where(UsuarioModel.email == email.value)
        )
        return _to_entity(model) if model is not None else None

    async def find_by_id(self, usuario_id: uuid.UUID) -> Usuario | None:
        model = await self._session.get(UsuarioModel, usuario_id)
        return _to_entity(model) if model is not None else None

    async def actualizar_password_hash(self, usuario_id: uuid.UUID, password_hash: str) -> None:
        await self._session.execute(
            update(UsuarioModel)
            .where(UsuarioModel.id == usuario_id)
            .values(password_hash=password_hash)
        )


def _to_model(usuario: Usuario) -> UsuarioModel:
    model = UsuarioModel(
        email=usuario.email,
        password_hash=usuario.password_hash,
        nombre_completo=usuario.nombre_completo,
        rol=usuario.rol,
        activo=usuario.activo,
        email_verificado=usuario.email_verificado,
        habeas_data_aceptado=usuario.habeas_data_aceptado,
        habeas_data_aceptado_en=usuario.habeas_data_aceptado_en,
        idioma=usuario.idioma.value,
    )
    if usuario.id is not None:
        model.id = usuario.id
    return model


def _to_entity(model: UsuarioModel) -> Usuario:
    return Usuario(
        id=model.id,
        email=model.email,
        password_hash=model.password_hash,
        nombre_completo=model.nombre_completo,
        rol=model.rol,
        activo=model.activo,
        email_verificado=model.email_verificado,
        habeas_data_aceptado=model.habeas_data_aceptado,
        habeas_data_aceptado_en=model.habeas_data_aceptado_en,
        idioma=Idioma(model.idioma),
        creado_en=model.creado_en,
        actualizado_en=model.actualizado_en,
    )
