"""Genera los Secrets del clúster en infra/k8s/secretos/secretos.yaml, que no se sube al repositorio.

Uso: python infra/k8s/generar_secretos.py
Sin dependencias. Si el archivo ya existe no lo toca: cambiar las contraseñas dejaría a los
servicios con unas distintas a las de las bases. Las URL de cada servicio y las de cada rol deben
coincidir, por eso salen todas de aquí. Las llaves JWT van aparte (ver README.md).
"""

import json
import secrets
import sys
from pathlib import Path

DESTINO = Path(__file__).resolve().parent / "secretos" / "secretos.yaml"
POSTGRES = "postgres-rw.turismo-datos.svc:5432"
RABBITMQ = "rabbitmq.turismo-datos.svc:5672"
VALKEY = "valkey.turismo-datos.svc:6379"


def clave() -> str:
    # Hexadecimal: va dentro de URLs sin tener que escaparla.
    return secrets.token_hex(24)


def secreto(nombre: str, namespace: str, datos: dict[str, str], tipo: str = "Opaque") -> str:
    lineas = [
        "apiVersion: v1",
        "kind: Secret",
        "metadata:",
        f"  name: {nombre}",
        f"  namespace: {namespace}",
        f"type: {tipo}",
        "stringData:",
    ]
    lineas += [f"  {k}: {json.dumps(v)}" for k, v in datos.items()]
    return "\n".join(lineas)


def main() -> int:
    if DESTINO.exists():
        print(f"{DESTINO} ya existe: no se cambia.")
        return 0

    roles = {s: clave() for s in ("iam", "catalog", "booking", "review", "recommendation")}
    rabbit = clave()
    valkey = clave()
    s3 = {s: (f"{s}_{secrets.token_hex(6)}", clave()) for s in ("catalog", "iam", "respaldos")}
    amqp = f"amqp://turismo:{rabbit}@{RABBITMQ}/"

    def pg(servicio: str, driver: str = "asyncpg") -> str:
        return f"postgresql+{driver}://{servicio}_user:{roles[servicio]}@{POSTGRES}/{servicio}_db"

    identidades = {
        "identities": [
            {
                "name": "catalog",
                "credentials": [{"accessKey": s3["catalog"][0], "secretKey": s3["catalog"][1]}],
                "actions": [f"{a}:catalogo-imagenes" for a in ("Read", "Write", "List", "Tagging")],
            },
            {
                "name": "iam",
                "credentials": [{"accessKey": s3["iam"][0], "secretKey": s3["iam"][1]}],
                "actions": [f"{a}:documentos-verificacion" for a in ("Read", "Write", "List")],
            },
            {
                "name": "respaldos",
                "credentials": [{"accessKey": s3["respaldos"][0], "secretKey": s3["respaldos"][1]}],
                "actions": [f"{a}:respaldos-postgres" for a in ("Read", "Write", "List")],
            },
            {"name": "anonymous", "actions": ["Read:catalogo-imagenes"]},
        ]
    }

    documentos = [
        secreto(
            f"postgres-rol-{servicio}",
            "turismo-datos",
            {"username": f"{servicio}_user", "password": contrasena},
            "kubernetes.io/basic-auth",
        )
        for servicio, contrasena in roles.items()
    ]
    documentos += [
        secreto(
            "postgres-respaldos",
            "turismo-datos",
            {"ACCESS_KEY_ID": s3["respaldos"][0], "SECRET_ACCESS_KEY": s3["respaldos"][1]},
        ),
        secreto(
            "rabbitmq-credenciales",
            "turismo-datos",
            {"RABBITMQ_DEFAULT_USER": "turismo", "RABBITMQ_DEFAULT_PASS": rabbit},
        ),
        secreto("valkey-credenciales", "turismo-datos", {"VALKEY_PASSWORD": valkey}),
        secreto("seaweedfs-identidades", "turismo-datos", {"s3.json": json.dumps(identidades)}),
        secreto(
            "iam-secretos",
            "turismo-app",
            {
                "DATABASE_URL": pg("iam"),
                "VALKEY_URL": f"redis://:{valkey}@{VALKEY}/2",
                "RABBITMQ_URL": amqp,
                "S3_ACCESS_KEY": s3["iam"][0],
                "S3_SECRET_KEY": s3["iam"][1],
                "SMTP_USUARIO": "",
                "SMTP_PASSWORD": "",
            },
        ),
        secreto(
            "catalog-secretos",
            "turismo-app",
            {
                "DATABASE_URL": pg("catalog"),
                "VALKEY_URL": f"redis://:{valkey}@{VALKEY}/0",
                "RABBITMQ_URL": amqp,
                "S3_ACCESS_KEY": s3["catalog"][0],
                "S3_SECRET_KEY": s3["catalog"][1],
                "SMTP_USUARIO": "",
                "SMTP_CLAVE": "",
                "INTENCION_VISITA_SECRETO": clave(),
            },
        ),
        secreto(
            "booking-service-secretos",
            "turismo-app",
            {
                "DATABASE_URL": pg("booking"),
                "VALKEY_URL": f"redis://:{valkey}@{VALKEY}/1",
                "RABBITMQ_URL": amqp,
            },
        ),
        secreto(
            "review-secretos",
            "turismo-app",
            {"DATABASE_URL": pg("review"), "RABBITMQ_URL": amqp},
        ),
        secreto(
            "recommendation-secretos",
            "turismo-app",
            {
                "DB_URL": pg("recommendation", "psycopg"),
                "VALKEY_URL": f"redis://:{valkey}@{VALKEY}/3",
                "LLM_API_KEY": "",
            },
        ),
    ]

    DESTINO.parent.mkdir(exist_ok=True)
    DESTINO.write_text("\n---\n".join(documentos) + "\n", encoding="utf-8", newline="\n")
    print(f"Secrets generados en {DESTINO}. Falta poner SMTP y LLM_API_KEY si se van a usar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
