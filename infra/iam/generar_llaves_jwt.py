"""Genera el par de llaves JWT de iam-service en el entorno local, solo si no existe.

Lo corre el servicio iam-llaves del compose. En k3s las llaves van en el Secret `iam-jwt-keys`.
"""

import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

USUARIO_IAM = 1000  # el de la imagen de iam-service

carpeta = Path(sys.argv[1])
privada = carpeta / "private.pem"
publica = carpeta / "public.pem"

if privada.exists() and publica.exists():
    print("Las llaves JWT ya existen: no se cambian.")
    sys.exit(0)

llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
privada.write_bytes(
    llave.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
)
publica.write_bytes(
    llave.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
)
for ruta, modo in ((privada, 0o400), (publica, 0o444)):
    os.chown(ruta, USUARIO_IAM, USUARIO_IAM)
    ruta.chmod(modo)
print("Llaves JWT generadas.")
