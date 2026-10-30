"""Genera contracts/openapi/iam.yaml desde la app. Uso: uv run python -m scripts.exportar_openapi

No necesita las llaves JWT ni ningún servicio: la app solo los usa al arrancar.
"""

from pathlib import Path
from typing import Any

import yaml

from app.config import Settings
from app.main import create_app

CONTRATO = Path(__file__).resolve().parents[3] / "contracts" / "openapi" / "iam.yaml"
CABECERA = "# Generado por services/iam-service/scripts/exportar_openapi.py: no editar a mano.\n"


def generar() -> dict[str, Any]:
    # Sin .env: el contrato no puede depender de la configuración de quien lo genera.
    return create_app(Settings(_env_file=None)).openapi()


def main() -> None:
    texto = yaml.safe_dump(generar(), sort_keys=False, allow_unicode=True, width=100)
    CONTRATO.write_text(CABECERA + texto, encoding="utf-8", newline="\n")
    print(f"Contrato escrito en {CONTRATO}")


if __name__ == "__main__":
    main()
