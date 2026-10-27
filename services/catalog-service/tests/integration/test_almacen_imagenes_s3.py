"""URL firmada contra un SeaweedFS real: solo sube el archivo con el tipo y tamaño firmados."""

import time
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import boto3
import httpx
import pytest

from app.domain.value_objects.imagen_solicitada import ImagenSolicitada, TipoImagen
from app.infrastructure.reloj import RelojSistema
from app.infrastructure.storage.almacen_imagenes_s3 import AlmacenImagenesS3

pytestmark = pytest.mark.integration

CONFIG_S3 = Path(__file__).resolve().parents[2] / "dev" / "seaweedfs-s3.json"
ACCESO, SECRETO, BUCKET = "catalog_access_dev", "catalog_secret_dev", "catalogo-imagenes"


@pytest.fixture(scope="module")
def endpoint() -> Iterator[str]:
    try:
        from testcontainers.core.container import DockerContainer

        contenedor = (
            DockerContainer("chrislusf/seaweedfs:3.80")
            .with_command(
                "server -ip.bind=0.0.0.0 -dir=/data -s3 -s3.port=8333 "
                "-s3.config=/etc/seaweedfs/s3.json -volume.max=2"
            )
            .with_volume_mapping(str(CONFIG_S3), "/etc/seaweedfs/s3.json", "ro")
            .with_exposed_ports(8333)
            .start()
        )
    except Exception as exc:
        pytest.skip(f"Docker no disponible: {exc}")
    url = f"http://{contenedor.get_container_host_ip()}:{contenedor.get_exposed_port(8333)}"
    s3 = boto3.client(
        "s3",
        endpoint_url=url,
        aws_access_key_id=ACCESO,
        aws_secret_access_key=SECRETO,
        region_name="us-east-1",
    )
    for _ in range(60):  # el gateway S3 arranca después del master y el filer
        try:
            s3.create_bucket(Bucket=BUCKET)
            break
        except Exception:
            time.sleep(1)
    else:
        contenedor.stop()
        pytest.fail("SeaweedFS no arrancó")
    yield url
    contenedor.stop()


def almacen(endpoint: str) -> AlmacenImagenesS3:
    return AlmacenImagenesS3(
        endpoint, "us-east-1", ACCESO, SECRETO, BUCKET, f"{endpoint}/{BUCKET}", RelojSistema()
    )


def test_sube_y_queda_publica(endpoint: str) -> None:
    contenido = b"\x89PNG" + b"0" * 96
    subida = almacen(endpoint).url_subida(uuid4(), ImagenSolicitada(TipoImagen.PNG, len(contenido)))
    r = httpx.put(subida.subida_url, content=contenido, headers={"Content-Type": "image/png"})
    assert r.status_code == 200
    publica = httpx.get(subida.url_publica)  # lectura anónima, sin firma
    assert publica.status_code == 200 and publica.content == contenido


@pytest.mark.parametrize(
    ("contenido", "tipo"),
    [(b"0" * 150, "image/png"), (b"0" * 100, "text/html")],
    ids=["otro_tamano", "otro_tipo"],
)
def test_rechaza_lo_que_no_se_firmo(endpoint: str, contenido: bytes, tipo: str) -> None:
    subida = almacen(endpoint).url_subida(uuid4(), ImagenSolicitada(TipoImagen.PNG, 100))
    r = httpx.put(subida.subida_url, content=contenido, headers={"Content-Type": tipo})
    assert r.status_code == 403
    assert httpx.get(subida.url_publica).status_code == 404


def test_sin_firma_no_se_puede_escribir(endpoint: str) -> None:
    r = httpx.put(f"{endpoint}/{BUCKET}/{uuid4()}/x.png", content=b"1")
    assert r.status_code == 403
