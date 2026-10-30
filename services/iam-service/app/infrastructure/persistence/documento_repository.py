import uuid
from datetime import datetime

from sqlalchemy import Integer, and_, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.documento_verificacion import (
    TIPOS_REQUERIDOS,
    DocumentoVerificacion,
    EstadoVerificacion,
)
from app.domain.value_objects.enums import EstadoDocumento, Rol, TipoDocumento
from app.domain.value_objects.filtro_prestadores import (
    FiltroPrestadores,
    PaginaPrestadores,
    ResumenPrestador,
)
from app.infrastructure.persistence.models import DocumentoVerificacion as DocumentoModel
from app.infrastructure.persistence.models import Usuario as UsuarioModel


class SqlAlchemyDocumentoRepository:
    """Implementa DocumentoRepository sobre documento_verificacion."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def agregar(self, documento: DocumentoVerificacion) -> DocumentoVerificacion:
        model = DocumentoModel(
            usuario_id=documento.usuario_id,
            tipo_documento=documento.tipo_documento,
            objeto_s3=documento.objeto_s3,
            tipo_contenido=documento.tipo_contenido,
            tamano_bytes=documento.tamano_bytes,
            estado=documento.estado,
            vigente=documento.vigente,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def vigentes(self, usuario_id: uuid.UUID) -> list[DocumentoVerificacion]:
        modelos = await self._session.scalars(
            select(DocumentoModel)
            .where(DocumentoModel.usuario_id == usuario_id, DocumentoModel.vigente.is_(True))
            .order_by(DocumentoModel.tipo_documento)
        )
        return [_to_entity(m) for m in modelos]

    async def historial(self, usuario_id: uuid.UUID) -> list[DocumentoVerificacion]:
        modelos = await self._session.scalars(
            select(DocumentoModel)
            .where(DocumentoModel.usuario_id == usuario_id)
            .order_by(DocumentoModel.fecha_subida.desc(), DocumentoModel.id)
        )
        return [_to_entity(m) for m in modelos]

    async def find_by_id(self, documento_id: uuid.UUID) -> DocumentoVerificacion | None:
        model = await self._session.get(DocumentoModel, documento_id)
        return _to_entity(model) if model is not None else None

    async def retirar_vigente(self, usuario_id: uuid.UUID, tipo: TipoDocumento) -> None:
        await self._session.execute(
            update(DocumentoModel)
            .where(
                DocumentoModel.usuario_id == usuario_id,
                DocumentoModel.tipo_documento == tipo,
                DocumentoModel.vigente.is_(True),
            )
            .values(vigente=False)
        )

    async def marcar_revisado(
        self,
        documento_id: uuid.UUID,
        estado: EstadoDocumento,
        revisado_por: uuid.UUID,
        revisado_en: datetime,
        motivo_rechazo: str | None,
    ) -> DocumentoVerificacion:
        model = await self._session.scalar(
            update(DocumentoModel)
            .where(DocumentoModel.id == documento_id)
            .values(
                estado=estado,
                revisado_por=revisado_por,
                revisado_en=revisado_en,
                motivo_rechazo=motivo_rechazo,
            )
            .returning(DocumentoModel)
            .execution_options(populate_existing=True)
        )
        assert model is not None
        return _to_entity(model)

    async def listar_prestadores(self, filtro: FiltroPrestadores) -> PaginaPrestadores:
        # Conteos de los vigentes por prestador; el estado se deriva igual que en
        # estado_verificacion() (rechazado > incompleto > aprobado > pendiente).
        d = DocumentoModel
        conteos = (
            select(
                d.usuario_id,
                func.count().label("cargados"),
                func.sum(case((d.estado == EstadoDocumento.RECHAZADO, 1), else_=0))
                .cast(Integer)
                .label("rechazados"),
                func.sum(case((d.estado == EstadoDocumento.APROBADO, 1), else_=0))
                .cast(Integer)
                .label("aprobados"),
            )
            .where(d.vigente.is_(True))
            .group_by(d.usuario_id)
            .subquery()
        )
        requeridos = len(TIPOS_REQUERIDOS)
        cargados = func.coalesce(conteos.c.cargados, 0)
        estado = case(
            (func.coalesce(conteos.c.rechazados, 0) > 0, EstadoVerificacion.RECHAZADO.value),
            (cargados < requeridos, EstadoVerificacion.INCOMPLETO.value),
            (conteos.c.aprobados == requeridos, EstadoVerificacion.APROBADO.value),
            else_=EstadoVerificacion.PENDIENTE.value,
        ).label("estado")
        u = UsuarioModel
        condiciones = [u.rol == Rol.PRESTADOR]
        if filtro.estado is not None:
            condiciones.append(estado == filtro.estado.value)
        base = select(u, estado).outerjoin(conteos, conteos.c.usuario_id == u.id)

        total = await self._session.scalar(
            select(func.count()).select_from(base.where(and_(*condiciones)).subquery())
        )
        filas = (
            await self._session.execute(
                base.where(*condiciones)
                .order_by(u.creado_en, u.id)
                .limit(filtro.tamano)
                .offset((filtro.pagina - 1) * filtro.tamano)
            )
        ).all()

        ids = [fila[0].id for fila in filas]
        vigentes: dict[uuid.UUID, list[DocumentoVerificacion]] = {i: [] for i in ids}
        if ids:
            documentos = await self._session.scalars(
                select(d)
                .where(d.usuario_id.in_(ids), d.vigente.is_(True))
                .order_by(d.tipo_documento)
            )
            for documento in documentos:
                vigentes[documento.usuario_id].append(_to_entity(documento))

        return PaginaPrestadores(
            items=[
                ResumenPrestador(
                    usuario_id=usuario.id,
                    nombre_completo=usuario.nombre_completo,
                    email=usuario.email,
                    activo=usuario.activo,
                    razon_social=usuario.razon_social,
                    estado=EstadoVerificacion(estado_fila),
                    vigentes=vigentes[usuario.id],
                )
                for usuario, estado_fila in filas
            ],
            total=total or 0,
            pagina=filtro.pagina,
            tamano=filtro.tamano,
        )


def _to_entity(model: DocumentoModel) -> DocumentoVerificacion:
    return DocumentoVerificacion(
        id=model.id,
        usuario_id=model.usuario_id,
        tipo_documento=model.tipo_documento,
        objeto_s3=model.objeto_s3,
        tipo_contenido=model.tipo_contenido,
        tamano_bytes=model.tamano_bytes,
        estado=model.estado,
        vigente=model.vigente,
        motivo_rechazo=model.motivo_rechazo,
        revisado_por=model.revisado_por,
        revisado_en=model.revisado_en,
        fecha_subida=model.fecha_subida,
    )
