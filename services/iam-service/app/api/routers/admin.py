"""UC27 (usuarios, roles y estado), UC28 (verificación de prestadores) y UC33 (bitácora).

Solo Admin.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import AwareDatetime

from app.api.dependencies import (
    get_abrir_documento,
    get_aprobar_prestador,
    get_cambiar_estado_usuario,
    get_cambiar_rol_usuario,
    get_consultar_bitacora,
    get_consultar_verificacion,
    get_listar_prestadores,
    get_listar_usuarios,
    get_obtener_usuario,
    get_rechazar_prestador,
    require_role,
)
from app.api.ip_origen import ip_origen
from app.api.schemas.admin import (
    CambioEstadoRequest,
    CambioRolRequest,
    EntradaBitacoraResponse,
    PaginaBitacoraResponse,
    PaginaUsuariosResponse,
    ResultadoTexto,
    RolTexto,
    UsuarioAdminResponse,
)
from app.api.schemas.documentos import (
    DocumentoAdminResponse,
    EnlaceDocumentoResponse,
    EstadoVerificacionTexto,
    PaginaPrestadoresResponse,
    RechazoRequest,
    ResumenPrestadorResponse,
    VerificacionAdminResponse,
)
from app.api.schemas.errors import ErrorResponse
from app.application.use_cases.abrir_documento import AbrirDocumento
from app.application.use_cases.aprobar_prestador import AprobarPrestador, AprobarPrestadorCommand
from app.application.use_cases.cambiar_estado_usuario import (
    CambiarEstadoCommand,
    CambiarEstadoUsuario,
)
from app.application.use_cases.cambiar_rol_usuario import CambiarRolCommand, CambiarRolUsuario
from app.application.use_cases.consultar_bitacora import ConsultarBitacora
from app.application.use_cases.consultar_verificacion import ConsultarVerificacion
from app.application.use_cases.listar_prestadores import ListarPrestadores
from app.application.use_cases.listar_usuarios import ListarUsuarios
from app.application.use_cases.obtener_usuario import ObtenerUsuario
from app.application.use_cases.rechazar_prestador import (
    DocumentoRechazado,
    RechazarPrestador,
    RechazarPrestadorCommand,
)
from app.domain.entities.documento_verificacion import EstadoVerificacion
from app.domain.value_objects.enums import ResultadoAuditoria, Rol, TipoDocumento
from app.domain.value_objects.filtro_bitacora import FiltroBitacora
from app.domain.value_objects.filtro_prestadores import FiltroPrestadores
from app.domain.value_objects.filtro_usuarios import FiltroUsuarios
from app.domain.value_objects.token import ClaimsToken

router = APIRouter(prefix="/api/iam/admin", tags=["admin"])

Admin = Annotated[ClaimsToken, Depends(require_role(Rol.ADMIN))]

_ERRORES_ACCESO: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "Token ausente, inválido, expirado o revocado (TOKEN_INVALIDO).",
    },
    status.HTTP_403_FORBIDDEN: {
        "model": ErrorResponse,
        "description": "El rol del usuario no es Admin (ROL_INSUFICIENTE).",
    },
}
_ERRORES_CAMBIO: dict[int | str, dict[str, Any]] = {
    **_ERRORES_ACCESO,
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "La cuenta no existe (USUARIO_NO_ENCONTRADO).",
    },
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "Cambio sobre la propia cuenta (AUTOGESTION_NO_PERMITIDA) o la "
        "plataforma quedaría sin Admins activos (ULTIMO_ADMIN).",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ErrorResponse,
        "description": "Valkey no responde: no se pudo revocar y no se cambió nada "
        "(SERVICIO_NO_DISPONIBLE).",
    },
}


@router.get("/usuarios", response_model=PaginaUsuariosResponse, responses=_ERRORES_ACCESO)
async def listar_usuarios(
    _: Admin,
    listar: Annotated[ListarUsuarios, Depends(get_listar_usuarios)],
    rol: RolTexto | None = None,
    activo: bool | None = None,
    q: Annotated[
        str | None, Query(max_length=100, description="Busca en el nombre y en el correo.")
    ] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginaUsuariosResponse:
    resultado = await listar.execute(
        FiltroUsuarios(
            rol=Rol(rol) if rol else None,
            activo=activo,
            q=(q or "").strip() or None,
            pagina=pagina,
            tamano=tamano,
        )
    )
    return PaginaUsuariosResponse(
        items=[UsuarioAdminResponse.model_validate(u) for u in resultado.items],
        total=resultado.total,
        pagina=resultado.pagina,
        tamano=resultado.tamano,
    )


@router.get(
    "/usuarios/{usuario_id}",
    response_model=UsuarioAdminResponse,
    responses={
        **_ERRORES_ACCESO,
        status.HTTP_404_NOT_FOUND: _ERRORES_CAMBIO[status.HTTP_404_NOT_FOUND],
    },
)
async def obtener_usuario(
    usuario_id: uuid.UUID,
    _: Admin,
    obtener: Annotated[ObtenerUsuario, Depends(get_obtener_usuario)],
) -> UsuarioAdminResponse:
    return UsuarioAdminResponse.model_validate(await obtener.execute(usuario_id))


@router.patch(
    "/usuarios/{usuario_id}/rol", response_model=UsuarioAdminResponse, responses=_ERRORES_CAMBIO
)
async def cambiar_rol(
    usuario_id: uuid.UUID,
    body: CambioRolRequest,
    request: Request,
    admin: Admin,
    cambiar: Annotated[CambiarRolUsuario, Depends(get_cambiar_rol_usuario)],
) -> UsuarioAdminResponse:
    """Revoca los tokens del usuario. Si deja de ser Prestador, publica `prestador.suspendido`."""
    usuario = await cambiar.execute(
        CambiarRolCommand(
            admin_id=uuid.UUID(admin.sub),
            usuario_id=usuario_id,
            motivo=body.motivo,
            ip_origen=ip_origen(request),
            rol=Rol(body.rol),
        )
    )
    return UsuarioAdminResponse.model_validate(usuario)


@router.patch(
    "/usuarios/{usuario_id}/estado",
    response_model=UsuarioAdminResponse,
    responses=_ERRORES_CAMBIO,
)
async def cambiar_estado(
    usuario_id: uuid.UUID,
    body: CambioEstadoRequest,
    request: Request,
    admin: Admin,
    cambiar: Annotated[CambiarEstadoUsuario, Depends(get_cambiar_estado_usuario)],
) -> UsuarioAdminResponse:
    """Desactivar revoca los tokens y, si es Prestador, publica `prestador.suspendido`."""
    usuario = await cambiar.execute(
        CambiarEstadoCommand(
            admin_id=uuid.UUID(admin.sub),
            usuario_id=usuario_id,
            motivo=body.motivo,
            ip_origen=ip_origen(request),
            activo=body.activo,
        )
    )
    return UsuarioAdminResponse.model_validate(usuario)


@router.get(
    "/bitacora",
    response_model=PaginaBitacoraResponse,
    responses={
        **_ERRORES_ACCESO,
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "Filtro inválido (VALIDACION; por ejemplo, una fecha sin zona "
            "horaria) o `desde` no es anterior a `hasta` (RANGO_FECHAS_INVALIDO).",
        },
    },
)
async def consultar_bitacora(
    request: Request,
    admin: Admin,
    consultar: Annotated[ConsultarBitacora, Depends(get_consultar_bitacora)],
    usuario_id: uuid.UUID | None = None,
    accion: Annotated[str | None, Query(max_length=50)] = None,
    resultado: ResultadoTexto | None = None,
    servicio_origen: Annotated[str | None, Query(max_length=50)] = None,
    desde: Annotated[
        AwareDatetime | None, Query(description="Inclusive. ISO 8601 con zona horaria.")
    ] = None,
    hasta: Annotated[
        AwareDatetime | None, Query(description="Exclusive. ISO 8601 con zona horaria.")
    ] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginaBitacoraResponse:
    """UC33: de la más reciente a la más antigua (por `fecha`, el momento del hecho).

    Cada consulta deja una fila `AUDIT_VIEW` con los filtros usados (C-43).
    """
    resultado_pagina = await consultar.execute(
        FiltroBitacora(
            usuario_id=usuario_id,
            accion=accion,
            resultado=ResultadoAuditoria(resultado) if resultado else None,
            servicio_origen=servicio_origen,
            desde=desde,
            hasta=hasta,
            pagina=pagina,
            tamano=tamano,
        ),
        admin_id=uuid.UUID(admin.sub),
        ip_origen=ip_origen(request),
    )
    return PaginaBitacoraResponse(
        items=[EntradaBitacoraResponse.model_validate(e) for e in resultado_pagina.items],
        total=resultado_pagina.total,
        pagina=resultado_pagina.pagina,
        tamano=resultado_pagina.tamano,
    )


_ERRORES_REVISION: dict[int | str, dict[str, Any]] = {
    **_ERRORES_ACCESO,
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "La cuenta no existe (USUARIO_NO_ENCONTRADO) o no hay un documento "
        "vigente de ese tipo (DOCUMENTO_NO_ENCONTRADO).",
    },
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "No es Prestador (NO_ES_PRESTADOR), le falta el RNT o el RUT "
        "(DOCUMENTOS_INCOMPLETOS) o el documento ya se revisó (DOCUMENTO_YA_REVISADO).",
    },
}


@router.get("/prestadores", response_model=PaginaPrestadoresResponse, responses=_ERRORES_ACCESO)
async def listar_prestadores(
    _: Admin,
    listar: Annotated[ListarPrestadores, Depends(get_listar_prestadores)],
    estado: EstadoVerificacionTexto | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginaPrestadoresResponse:
    """UC28: cola de revisión (`estado=pendiente`), de la cuenta más antigua a la más nueva."""
    resultado = await listar.execute(
        FiltroPrestadores(
            estado=EstadoVerificacion(estado) if estado else None, pagina=pagina, tamano=tamano
        )
    )
    return PaginaPrestadoresResponse(
        items=[
            ResumenPrestadorResponse(
                usuario_id=p.usuario_id,
                nombre_completo=p.nombre_completo,
                email=p.email,
                activo=p.activo,
                razon_social=p.razon_social,
                estado=p.estado,
                documentos=[DocumentoAdminResponse.model_validate(d) for d in p.vigentes],
            )
            for p in resultado.items
        ],
        total=resultado.total,
        pagina=resultado.pagina,
        tamano=resultado.tamano,
    )


@router.get(
    "/prestadores/{usuario_id}/documentos",
    response_model=VerificacionAdminResponse,
    responses=_ERRORES_REVISION,
)
async def documentos_de_prestador(
    usuario_id: uuid.UUID,
    _: Admin,
    consultar: Annotated[ConsultarVerificacion, Depends(get_consultar_verificacion)],
) -> VerificacionAdminResponse:
    """Historial completo, incluidos los documentos reemplazados (`vigente: false`)."""
    resultado = await consultar.execute(usuario_id, historial=True)
    return VerificacionAdminResponse.model_validate(resultado, from_attributes=True)


@router.get(
    "/documentos/{documento_id}/url",
    response_model=EnlaceDocumentoResponse,
    responses={
        **_ERRORES_ACCESO,
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "El documento no existe (DOCUMENTO_NO_ENCONTRADO).",
        },
    },
)
async def abrir_documento(
    documento_id: uuid.UUID,
    request: Request,
    admin: Admin,
    abrir: Annotated[AbrirDocumento, Depends(get_abrir_documento)],
) -> EnlaceDocumentoResponse:
    """URL de 5 minutos para ver el documento. Cada consulta queda como `DOCUMENT_VIEW`."""
    enlace = await abrir.execute(
        documento_id, admin_id=uuid.UUID(admin.sub), ip_origen=ip_origen(request)
    )
    return EnlaceDocumentoResponse(url=enlace.url, expira_en=enlace.expira_en)


@router.post(
    "/prestadores/{usuario_id}/aprobar",
    response_model=VerificacionAdminResponse,
    responses=_ERRORES_REVISION,
)
async def aprobar_prestador(
    usuario_id: uuid.UUID,
    request: Request,
    admin: Admin,
    aprobar: Annotated[AprobarPrestador, Depends(get_aprobar_prestador)],
) -> VerificacionAdminResponse:
    """Aprueba el RNT y el RUT vigentes y, si la cuenta está activa, publica
    `prestador.aprobado`."""
    resultado = await aprobar.execute(
        AprobarPrestadorCommand(
            admin_id=uuid.UUID(admin.sub), usuario_id=usuario_id, ip_origen=ip_origen(request)
        )
    )
    return VerificacionAdminResponse.model_validate(resultado, from_attributes=True)


@router.post(
    "/prestadores/{usuario_id}/rechazar",
    response_model=VerificacionAdminResponse,
    responses=_ERRORES_REVISION,
)
async def rechazar_prestador(
    usuario_id: uuid.UUID,
    body: RechazoRequest,
    request: Request,
    admin: Admin,
    rechazar: Annotated[RechazarPrestador, Depends(get_rechazar_prestador)],
) -> VerificacionAdminResponse:
    """Rechaza los documentos indicados, con el motivo que verá el prestador."""
    resultado = await rechazar.execute(
        RechazarPrestadorCommand(
            admin_id=uuid.UUID(admin.sub),
            usuario_id=usuario_id,
            documentos=[
                DocumentoRechazado(tipo=TipoDocumento(d.tipo), motivo=d.motivo)
                for d in body.documentos
            ],
            ip_origen=ip_origen(request),
        )
    )
    return VerificacionAdminResponse.model_validate(resultado, from_attributes=True)
