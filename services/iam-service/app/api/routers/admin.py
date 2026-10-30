from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import require_role
from app.api.schemas.errors import ErrorResponse
from app.domain.value_objects.enums import Rol
from app.domain.value_objects.token import ClaimsToken

router = APIRouter(prefix="/api/iam/admin", tags=["admin"])


# TEMPORAL: prueba el RBAC hasta que existan los endpoints de administración (bloque 4).
@router.get(
    "/ping",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Token ausente, inválido, expirado o revocado (TOKEN_INVALIDO).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "El rol del usuario no es Admin (ROL_INSUFICIENTE).",
        },
    },
)
async def ping(_: Annotated[ClaimsToken, Depends(require_role(Rol.ADMIN))]) -> dict[str, bool]:
    return {"ok": True}
