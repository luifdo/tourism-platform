import uuid
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.usuario import NOMBRE_SUPRIMIDO, Usuario, email_suprimido
from app.domain.exceptions import UsuarioYaExisteError
from app.domain.value_objects.email import Email
from app.domain.value_objects.enums import Idioma, Rol
from app.domain.value_objects.filtro_usuarios import FiltroUsuarios, PaginaUsuarios
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

    async def listar(self, filtro: FiltroUsuarios) -> PaginaUsuarios:
        condiciones = []
        if filtro.rol is not None:
            condiciones.append(UsuarioModel.rol == filtro.rol)
        if filtro.activo is not None:
            condiciones.append(UsuarioModel.activo == filtro.activo)
        if filtro.q:
            patron = f"%{_escapar_like(filtro.q)}%"
            condiciones.append(
                or_(
                    UsuarioModel.nombre_completo.ilike(patron, escape="\\"),
                    UsuarioModel.email.ilike(patron, escape="\\"),
                )
            )
        total = await self._session.scalar(
            select(func.count()).select_from(UsuarioModel).where(*condiciones)
        )
        modelos = await self._session.scalars(
            select(UsuarioModel)
            .where(*condiciones)
            .order_by(UsuarioModel.creado_en.desc(), UsuarioModel.id)
            .limit(filtro.tamano)
            .offset((filtro.pagina - 1) * filtro.tamano)
        )
        return PaginaUsuarios(
            items=[_to_entity(m) for m in modelos],
            total=total or 0,
            pagina=filtro.pagina,
            tamano=filtro.tamano,
        )

    async def bloquear_admins_activos(self) -> int:
        ids = await self._session.scalars(
            select(UsuarioModel.id)
            .where(UsuarioModel.rol == Rol.ADMIN, UsuarioModel.activo.is_(True))
            .order_by(UsuarioModel.id)
            .with_for_update()
        )
        return len(ids.all())

    async def find_by_id_para_actualizar(self, usuario_id: uuid.UUID) -> Usuario | None:
        # populate_existing: si la fila ya estaba en la sesión, se relee con el bloqueo puesto.
        model = await self._session.scalar(
            select(UsuarioModel)
            .where(UsuarioModel.id == usuario_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return _to_entity(model) if model is not None else None

    async def actualizar_razon_social(self, usuario_id: uuid.UUID, razon_social: str) -> None:
        await self._session.execute(
            update(UsuarioModel)
            .where(UsuarioModel.id == usuario_id)
            .values(razon_social=razon_social)
        )

    async def actualizar_rol_y_estado(
        self, usuario_id: uuid.UUID, rol: Rol, activo: bool
    ) -> Usuario:
        model = await self._session.scalar(
            update(UsuarioModel)
            .where(UsuarioModel.id == usuario_id)
            .values(rol=rol, activo=activo)
            .returning(UsuarioModel)
            .execution_options(populate_existing=True)
        )
        assert model is not None
        return _to_entity(model)

    async def actualizar_perfil(
        self, usuario_id: uuid.UUID, nombre_completo: str, idioma: Idioma
    ) -> Usuario:
        model = await self._session.scalar(
            update(UsuarioModel)
            .where(UsuarioModel.id == usuario_id)
            .values(
                nombre_completo=nombre_completo,
                idioma=idioma.value,
                version=UsuarioModel.version + 1,
            )
            .returning(UsuarioModel)
            .execution_options(populate_existing=True)
        )
        assert model is not None
        return _to_entity(model)

    async def suprimir_datos(
        self, usuario_id: uuid.UUID, password_hash: str, suprimido_en: datetime
    ) -> None:
        await self._session.execute(
            update(UsuarioModel)
            .where(UsuarioModel.id == usuario_id)
            .values(
                email=email_suprimido(usuario_id),
                nombre_completo=NOMBRE_SUPRIMIDO,
                razon_social=None,
                activo=False,
                password_hash=password_hash,
                datos_suprimidos_en=suprimido_en,
                version=UsuarioModel.version + 1,
            )
        )


def _escapar_like(texto: str) -> str:
    """El texto del Admin se busca literal: `%` y `_` no son comodines."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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
        razon_social=model.razon_social,
        version=model.version,
        datos_suprimidos_en=model.datos_suprimidos_en,
        creado_en=model.creado_en,
        actualizado_en=model.actualizado_en,
    )
