"""Crea en SeaweedFS el bucket privado de documentos de verificación. Es idempotente.

Uso: uv run python -m scripts.crear_bucket
Lee S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY y S3_BUCKET del entorno o del .env.

Solo para desarrollo: en k3s el bucket y las credenciales del IAM los provee infra/, porque
allí SeaweedFS usa un archivo de identidades (C-46).
"""

import sys

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings


def crear_bucket(endpoint: str, region: str, access_key: str, secret_key: str, bucket: str) -> bool:
    """Devuelve True si lo creó y False si ya existía."""
    cliente = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    try:
        cliente.head_bucket(Bucket=bucket)
        return False
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket"}:
            raise
    cliente.create_bucket(Bucket=bucket)
    return True


def main() -> int:
    s = get_settings()
    try:
        creado = crear_bucket(
            s.s3_endpoint_url, s.s3_region, s.s3_access_key, s.s3_secret_key, s.s3_bucket
        )
    except (BotoCoreError, ClientError) as exc:
        print(f"SeaweedFS no respondió en {s.s3_endpoint_url}: {exc}", file=sys.stderr)
        return 1
    print(f"Bucket {s.s3_bucket} {'creado' if creado else 'ya existía'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
