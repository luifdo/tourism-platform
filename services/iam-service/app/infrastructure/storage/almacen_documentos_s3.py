"""Documentos de verificación en SeaweedFS con su API S3 (implementa AlmacenDocumentos).

* El bucket es privado: nadie lee un objeto sin una URL firmada.
* Dos clientes: el interno sube los archivos desde el IAM; el público solo firma URLs, con
  el host al que llega el navegador del Admin (la firma SigV4 incluye el host, como en
  catalog). Firmar se calcula localmente, sin llamar a SeaweedFS.
* La URL fija el tipo de contenido y el nombre con que se muestra el archivo
  (`RNT.pdf`), no la llave interna (C-30).
* boto3 es síncrono: las llamadas corren en hilos propios para no frenar el event loop ni
  competir con Argon2, que usa los del bucle (C-59). Los clientes se crean al primer uso
  (crearlos cuesta y la mayoría de las peticiones no los necesita).
* Tres intentos de 5 s no caben en lo que debe tardar el 503: cada llamada tiene además un tope
  total, que incluye la espera por un hilo libre. boto3 no se puede interrumpir, así que al
  vencer el tope el hilo sigue hasta agotar sus intentos.
"""

import asyncio
import contextvars
import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property, partial
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.domain.exceptions import ServicioNoDisponibleError
from app.domain.ports.almacen_documentos import VALIDEZ_URL

logger = logging.getLogger(__name__)


def _cliente(endpoint: str, region: str, access_key: str, secret_key: str):  # type: ignore[no-untyped-def]
    # Una sesión por cliente: la sesión por defecto de boto3 no se puede usar entre hilos.
    return boto3.session.Session().client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=2,
            read_timeout=5,
            # max_attempts cuenta los reintentos: son 3 intentos en total.
            retries={"max_attempts": 2, "mode": "standard"},
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
        hilos_maximos: int = 8,
        tiempo_maximo_segundos: float = 9.0,
    ) -> None:
        self._endpoint_interno = endpoint_interno
        self._endpoint_publico = endpoint_publico
        self._credenciales = (region, access_key, secret_key)
        self._bucket = bucket
        self._hilos = ThreadPoolExecutor(max_workers=hilos_maximos, thread_name_prefix="s3")
        self._tiempo_maximo = tiempo_maximo_segundos
        self._creando_interno = threading.Lock()

    @cached_property
    def _interno(self):  # type: ignore[no-untyped-def]
        return _cliente(self._endpoint_interno, *self._credenciales)

    @cached_property
    def _publico(self):  # type: ignore[no-untyped-def]
        return _cliente(self._endpoint_publico, *self._credenciales)

    def _interno_en_hilo(self):  # type: ignore[no-untyped-def]
        # Crearlo tarda: en un hilo, para no frenar el bucle y que cuente dentro del tope, y una
        # sola vez aunque el primer uso llegue desde varios hilos.
        with self._creando_interno:
            return self._interno

    def cerrar(self) -> None:
        self._hilos.shutdown(wait=False, cancel_futures=True)

    async def _en_hilo[T](self, llamada: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        # copy_context, como asyncio.to_thread: los logs del hilo conservan el correlation_id.
        contexto = contextvars.copy_context()
        hilo = asyncio.get_running_loop().run_in_executor(
            self._hilos, partial(contexto.run, llamada, *args, **kwargs)
        )
        # Al vencer se cancela lo que aún espera un hilo; lo que ya corre termina por su cuenta.
        async with asyncio.timeout(self._tiempo_maximo):
            return await hilo

    async def guardar(self, clave: str, contenido: bytes, tipo_contenido: str) -> None:
        try:
            await self._en_hilo(self._guardar, clave, contenido, tipo_contenido)
        except (BotoCoreError, ClientError, TimeoutError) as exc:
            logger.error("SeaweedFS no guardó el documento: %s", type(exc).__name__)
            raise ServicioNoDisponibleError() from exc

    async def borrar_prefijo(self, prefijo: str) -> int:
        try:
            return await self._en_hilo(self._borrar_prefijo, prefijo)
        except (BotoCoreError, ClientError, TimeoutError) as exc:
            logger.error("SeaweedFS no borró los documentos: %s", type(exc).__name__)
            raise ServicioNoDisponibleError() from exc

    def _guardar(self, clave: str, contenido: bytes, tipo_contenido: str) -> None:
        self._interno_en_hilo().put_object(
            Bucket=self._bucket, Key=clave, Body=contenido, ContentType=tipo_contenido
        )

    def _borrar_prefijo(self, prefijo: str) -> int:
        borrados = 0
        interno = self._interno_en_hilo()
        paginas = interno.get_paginator("list_objects_v2").paginate(
            Bucket=self._bucket, Prefix=prefijo
        )
        for pagina in paginas:
            claves = [{"Key": objeto["Key"]} for objeto in pagina.get("Contents", [])]
            if not claves:
                continue
            respuesta = interno.delete_objects(
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
