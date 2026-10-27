"""Imágenes del catálogo en SeaweedFS con su API S3 (implementa AlmacenImagenes).

* La URL firmada se calcula localmente (sin llamar a SeaweedFS), con el host público al que
  llega el navegador: la firma SigV4 incluye el host.
* Se firman el tipo y el tamaño: si la PWA sube otro archivo, SeaweedFS rechaza la firma.
* Cada imagen queda en `{prestador_id}/{uuid}.{ext}`; los nombres no se pueden adivinar ni
  pisar entre prestadores.
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import boto3
from botocore.config import Config

from app.application.dto.subida_imagen import SubidaImagen
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.imagen_solicitada import ImagenSolicitada

VALIDEZ = timedelta(minutes=10)


class AlmacenImagenesS3:
    def __init__(
        self,
        endpoint_publico: str,
        region: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        url_publica_base: str,
        reloj: Reloj,
    ) -> None:
        self._cliente = boto3.client(
            "s3",
            endpoint_url=endpoint_publico,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self._bucket = bucket
        self._base = url_publica_base.rstrip("/")
        self._reloj = reloj

    def url_subida(self, prestador_id: UUID, imagen: ImagenSolicitada) -> SubidaImagen:
        clave = f"{prestador_id}/{uuid4()}.{imagen.tipo.extension}"
        subida_url = self._cliente.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": clave,
                "ContentType": imagen.tipo.value,
                "ContentLength": imagen.tamano_bytes,
            },
            ExpiresIn=int(VALIDEZ.total_seconds()),
        )
        ahora: datetime = self._reloj.ahora()
        return SubidaImagen(
            subida_url=subida_url, url_publica=f"{self._base}/{clave}", expira_en=ahora + VALIDEZ
        )

    def origen_de(self, prestador_id: UUID) -> str:
        return f"{self._base}/{prestador_id}/"
