"""Documentos de verificación en SeaweedFS con su API S3 (implementa AlmacenDocumentos).

* El bucket es privado: nadie lee un objeto sin una URL firmada.
* Dos clientes: el interno sube los archivos desde el IAM; el público solo firma URLs, con
  el host al que llega el navegador del Admin (la firma SigV4 incluye el host, como en
  catalog). Firmar se calcula localmente, sin llamar a SeaweedFS.
* La URL fija el tipo de contenido y el nombre con que se muestra el archivo
  (`RNT.pdf`), no la llave interna (C-30).
* boto3 es síncrono: la subida corre en un hilo para no frenar el event loop. Los clientes
  se crean al primer uso (crearlos cuesta y la mayoría de las peticiones no los necesita).
"""

import asyncio
import logging
from functools import cached_property

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.domain.exceptions import ServicioNoDisponibleError
from app.domain.ports.almacen_documentos import VALIDEZ_URL

logger = logging.getLogger(__name__)


def _cliente(endpoint: str, region: str, access_key: str, secret_key: str):  # type: ignore[no-untyped-def]
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=2,
            read_timeout=10,
            retries={"max_attempts": 2},
        ),
    )


class AlmacenDocumentosS3:
    def __init__(
        self,
        endpoint_interno: str,
        endpoint_publico: str,
        region: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ) -> None:
        self._endpoint_interno = endpoint_interno
        self._endpoint_publico = endpoint_publico
        self._credenciales = (region, access_key, secret_key)
        self._bucket = bucket

    @cached_property
    def _interno(self):  # type: ignore[no-untyped-def]
        return _cliente(self._endpoint_interno, *self._credenciales)

    @cached_property
    def _publico(self):  # type: ignore[no-untyped-def]
        return _cliente(self._endpoint_publico, *self._credenciales)

    async def guardar(self, clave: str, contenido: bytes, tipo_contenido: str) -> None:
        try:
            await asyncio.to_thread(
                self._interno.put_object,
                Bucket=self._bucket,
                Key=clave,
                Body=contenido,
                ContentType=tipo_contenido,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.error("SeaweedFS no guardó el documento: %s", type(exc).__name__)
            raise ServicioNoDisponibleError() from exc

    async def borrar_prefijo(self, prefijo: str) -> int:
        try:
            return await asyncio.to_thread(self._borrar_prefijo, prefijo)
        except (BotoCoreError, ClientError) as exc:
            logger.error("SeaweedFS no borró los documentos: %s", type(exc).__name__)
            raise ServicioNoDisponibleError() from exc

    def _borrar_prefijo(self, prefijo: str) -> int:
        borrados = 0
        paginas = self._interno.get_paginator("list_objects_v2").paginate(
            Bucket=self._bucket, Prefix=prefijo
        )
        for pagina in paginas:
            claves = [{"Key": objeto["Key"]} for objeto in pagina.get("Contents", [])]
            if not claves:
                continue
            respuesta = self._interno.delete_objects(
                Bucket=self._bucket, Delete={"Objects": claves, "Quiet": True}
            )
            # delete_objects responde 200 aunque falle algún objeto: los errores van en el cuerpo.
            if respuesta.get("Errors"):
                logger.error("SeaweedFS no borró %d objetos", len(respuesta["Errors"]))
                raise ServicioNoDisponibleError()
            borrados += len(claves)
        return borrados

    def url_lectura(self, clave: str, tipo_contenido: str, nombre_archivo: str) -> str:
        return self._publico.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": clave,
                "ResponseContentType": tipo_contenido,
                "ResponseContentDisposition": f"inline; filename={nombre_archivo}",
            },
            ExpiresIn=int(VALIDEZ_URL.total_seconds()),
        )
