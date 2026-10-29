"""Valida cuerpos de respuesta contra los contratos de contracts/openapi/."""

from functools import cache
from pathlib import Path

import yaml
from openapi_schema_validator import OAS30Validator, oas30_format_checker

CONTRATOS = Path(__file__).parents[3] / "contracts" / "openapi"


@cache
def contrato(archivo: str) -> dict:
    return yaml.safe_load((CONTRATOS / archivo).read_text(encoding="utf-8"))


def validar(archivo: str, ruta: str, estado: int, cuerpo: object, metodo: str = "get") -> None:
    """Lanza jsonschema.ValidationError si `cuerpo` no cumple la respuesta del contrato."""
    especificacion = contrato(archivo)
    respuesta = especificacion["paths"][ruta][metodo]["responses"][str(estado)]
    if "$ref" in respuesta:
        nombre = respuesta["$ref"].rsplit("/", 1)[1]
        respuesta = especificacion["components"]["responses"][nombre]
    esquema = respuesta["content"]["application/json"]["schema"]
    # Los $ref del contrato son locales (#/components/...): se resuelven en esta raíz.
    raiz = {"components": especificacion["components"], **esquema}
    OAS30Validator(raiz, format_checker=oas30_format_checker).validate(cuerpo)
