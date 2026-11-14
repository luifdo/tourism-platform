"""UC37: el prestador carga sus documentos de verificación (RNT y RUT) y ve su estado."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status

from app.api.dependencies import (
    get_consultar_verificacion,
    get_subir_documento,
    require_role,
)
from app.api.ip_origen import ip_origen
from app.api.schemas.documentos import DocumentoResponse, TipoTexto, VerificacionResponse
from app.api.schemas.errors import ErrorResponse
from app.application.use_cases.consultar_verificacion import ConsultarVerificacion
from app.application.use_cases.subir_documento import SubirDocumento, SubirDocumentoCommand
from app.domain.value_objects.archivo_documento import TAMANO_MAXIMO
from app.domain.value_objects.enums import Rol, TipoDocumento
from app.domain.value_objects.token import ClaimsToken

router = APIRouter(
    prefix="/api/iam/prestador",
    tags=["prestador"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "TOKEN_INVALIDO"},
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "El rol no es Prestador (ROL_INSUFICIENTE).",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "La cuenta ya no existe (USUARIO_NO_ENCONTRADO).",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": "Valkey no responde: no se puede comprobar la revocación del token "
            "(SERVICIO_NO_DISPONIBLE).",
        },
    },
)

Prestador = Annotated[ClaimsToken, Depends(require_role(Rol.PRESTADOR))]


@router.post(
    "/documentos",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentoResponse,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "El documento vigente de ese tipo ya fue aprobado (DOCUMENTO_APROBADO) "
            "o la cuenta suprimió sus datos durante la carga (CUENTA_SUPRIMIDA).",
        },
        status.HTTP_413_CONTENT_TOO_LARGE: {
            "model": ErrorResponse,
            "description": "El archivo supera los 5 MB (ARCHIVO_DEMASIADO_GRANDE).",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "No es PDF, JPG ni PNG (TIPO_ARCHIVO_NO_PERMITIDO), falta la razón "
            "social con el RUT (RAZON_SOCIAL_INVALIDA) o el formulario no es válido "
            "(VALIDACION).",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": "Valkey o SeaweedFS no responden (SERVICIO_NO_DISPONIBLE).",
        },
    },
)
async def subir_documento(
    request: Request,
    prestador: Prestador,
    subir: Annotated[SubirDocumento, Depends(get_subir_documento)],
    tipo: Annotated[TipoTexto, Form()],
    archivo: Annotated[UploadFile, File(description="PDF, JPG o PNG de hasta 5 MB.")],
    razon_social: Annotated[
        str | None, Form(max_length=200, description="Obligatoria con el RUT (C-07).")
    ] = None,
) -> DocumentoResponse:
    # Un byte de más basta para saber que supera el límite, sin leer el resto.
    contenido = await archivo.read(TAMANO_MAXIMO + 1)
    documento = await subir.execute(
        SubirDocumentoCommand(
            usuario_id=uuid.UUID(prestador.sub),
            tipo=TipoDocumento(tipo),
            contenido=contenido,
            razon_social=razon_social,
            ip_origen=ip_origen(request),
        )
    )
    return DocumentoResponse.model_validate(documento)


@router.get("/documentos", response_model=VerificacionResponse)
async def mis_documentos(
    prestador: Prestador,
    consultar: Annotated[ConsultarVerificacion, Depends(get_consultar_verificacion)],
) -> VerificacionResponse:
    """Documentos vigentes, con su estado y el motivo si se rechazaron."""
    resultado = await consultar.execute(uuid.UUID(prestador.sub))
    return VerificacionResponse.model_validate(resultado, from_attributes=True)
