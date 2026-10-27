from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_listar_zonas
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.schemas.zona_respuesta import ZonaRespuesta
from app.application.use_cases.listar_zonas import ListarZonas
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/catalog", tags=["Catálogo"])


@router.get("/zonas", summary="Listar las zonas activas", response_model=list[ZonaRespuesta])
async def listar_zonas(
    idioma: Annotated[Idioma, Depends(idioma_peticion)],
    listar: Annotated[ListarZonas, Depends(get_listar_zonas)],
) -> list[ZonaRespuesta]:
    zonas = [ZonaRespuesta.desde(z, idioma) for z in await listar.execute()]
    # Orden alfabético en el idioma pedido, que es como el usuario las busca en la lista.
    return sorted(zonas, key=lambda z: z.nombre.casefold())
