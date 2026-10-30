"""AlmacenDocumentosS3 contra el SeaweedFS de docker-compose.dev.yml (C-30).

Usa un bucket de pruebas propio. Se omite si SeaweedFS no responde. En desarrollo SeaweedFS
no tiene archivo de identidades: acepta cualquier credencial y no comprueba las firmas (una
URL alterada o sin firmar también responde 200). Por eso aquí no se puede probar que el
bucket sea privado ni que la firma proteja el nombre y el tipo; eso depende de la
configuración de infra/ en k3s (C-46).
"""

import uuid
from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings
from app.domain.exceptions import ServicioNoDisponibleError
from app.infrastructure.storage.almacen_documentos_s3 import AlmacenDocumentosS3
from scripts.crear_bucket import crear_bucket
from tests.unit.test_documentos_dominio import PDF

pytestmark = pytest.mark.s3

BUCKET = "iam-pruebas"


@pytest.fixture(scope="module")
def almacen() -> Iterator[AlmacenDocumentosS3]:
    s = get_settings()
    try:
        crear_bucket(s.s3_endpoint_url, s.s3_region, s.s3_access_key, s.s3_secret_key, BUCKET)
    except (BotoCoreError, ClientError) as exc:
        pytest.skip(f"SeaweedFS no responde: {type(exc).__name__}")
    yield AlmacenDocumentosS3(
        endpoint_interno=s.s3_endpoint_url,
        endpoint_publico=s.s3_endpoint_publico,
        region=s.s3_region,
        access_key=s.s3_access_key,
        secret_key=s.s3_secret_key,
        bucket=BUCKET,
    )


async def test_guardar_y_leer_con_la_url_prefirmada(almacen: AlmacenDocumentosS3) -> None:
    clave = f"{uuid.uuid4()}/RUT/{uuid.uuid4()}.pdf"

    await almacen.guardar(clave, PDF, "application/pdf")
    url = almacen.url_lectura(clave, "application/pdf", "RUT.pdf")

    async with httpx.AsyncClient(timeout=5) as http:
        respuesta = await http.get(url)
    assert respuesta.status_code == 200
    assert respuesta.content == PDF
    # El navegador muestra el archivo con su tipo real y como RUT.pdf, no con la llave.
    assert respuesta.headers["content-type"] == "application/pdf"
    assert respuesta.headers["content-disposition"] == "inline; filename=RUT.pdf"
    consulta = parse_qs(urlparse(url).query)
    assert consulta["X-Amz-Expires"] == ["300"]
    assert clave.split("/")[-1] in urlparse(url).path


async def test_borrar_prefijo_solo_borra_ese_usuario_y_es_idempotente(
    almacen: AlmacenDocumentosS3,
) -> None:
    usuario, otro = uuid.uuid4(), uuid.uuid4()
    propias = [f"{usuario}/RUT/{uuid.uuid4()}.pdf", f"{usuario}/RNT/{uuid.uuid4()}.pdf"]
    ajena = f"{otro}/RUT/{uuid.uuid4()}.pdf"
    for clave in [*propias, ajena]:
        await almacen.guardar(clave, PDF, "application/pdf")

    assert await almacen.borrar_prefijo(f"{usuario}/") == 2
    assert await almacen.borrar_prefijo(f"{usuario}/") == 0

    async with httpx.AsyncClient(timeout=5) as http:
        for clave in propias:
            url = almacen.url_lectura(clave, "application/pdf", "x.pdf")
            assert (await http.get(url)).status_code == 404
        url = almacen.url_lectura(ajena, "application/pdf", "x.pdf")
        assert (await http.get(url)).status_code == 200
    await almacen.borrar_prefijo(f"{otro}/")


async def test_borrar_prefijo_con_mas_de_una_pagina(almacen: AlmacenDocumentosS3) -> None:
    # Más de lo que devuelve una página con la prueba forzada a un tamaño pequeño.
    usuario = uuid.uuid4()
    claves = [f"{usuario}/RUT/{i}.pdf" for i in range(5)]
    for clave in claves:
        await almacen.guardar(clave, PDF, "application/pdf")
    paginador = almacen._interno.get_paginator("list_objects_v2")
    original = paginador.paginate

    def en_paginas_de_dos(**kwargs):  # type: ignore[no-untyped-def]
        return original(**kwargs, PaginationConfig={"PageSize": 2})

    paginador.paginate = en_paginas_de_dos  # type: ignore[method-assign]
    get_paginator = almacen._interno.get_paginator
    almacen._interno.get_paginator = lambda _: paginador  # type: ignore[method-assign]
    try:
        assert await almacen.borrar_prefijo(f"{usuario}/") == 5
    finally:
        almacen._interno.get_paginator = get_paginator  # type: ignore[method-assign]


async def test_seaweedfs_caido_al_borrar_es_servicio_no_disponible() -> None:
    caido = AlmacenDocumentosS3(
        endpoint_interno="http://127.0.0.1:1",
        endpoint_publico="http://127.0.0.1:1",
        region="us-east-1",
        access_key="x",
        secret_key="y",
        bucket=BUCKET,
    )

    with pytest.raises(ServicioNoDisponibleError):
        await caido.borrar_prefijo("a/")


async def test_seaweedfs_caido_es_servicio_no_disponible() -> None:
    caido = AlmacenDocumentosS3(
        endpoint_interno="http://127.0.0.1:1",
        endpoint_publico="http://127.0.0.1:1",
        region="us-east-1",
        access_key="x",
        secret_key="y",
        bucket=BUCKET,
    )

    with pytest.raises(ServicioNoDisponibleError):
        await caido.guardar("a/b.pdf", PDF, "application/pdf")
