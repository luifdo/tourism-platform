from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_listar_alertas
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.schemas.alerta_respuesta import AlertaRespuesta
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.application.use_cases.listar_alertas import ListarAlertas
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/catalog", tags=["Catálogo"])


@router.get(
    "/alertas",
    summary="Alertas oficiales vigentes (UC26)",
    response_model=list[AlertaRespuesta],
    responses={400: {"model": ErrorRespuesta}},
)
async def listar_alertas(
    idioma: Annotated[Idioma, Depends(idioma_peticion)],
    listar: Annotated[ListarAlertas, Depends(get_listar_alertas)],
    zona: Annotated[str | None, Query(pattern=r"^[a-z0-9-]{2,40}$")] = None,
    servicio_id: UUID | None = None,
) -> list[AlertaRespuesta]:
    alertas = await listar.execute(zona=zona, servicio_id=servicio_id)
    return [AlertaRespuesta.desde(a, idioma) for a in alertas]
