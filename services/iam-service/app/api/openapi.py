from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

_ERROR_VALIDACION = {
    "description": "La petición no cumple el esquema (VALIDACION, con la lista 'errores').",
    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
}


def esquema_openapi(app: FastAPI) -> dict[str, Any]:
    """El esquema de FastAPI con el 422 real: el servicio nunca responde `HTTPValidationError`."""
    if app.openapi_schema is None:
        esquema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        for operaciones in esquema["paths"].values():
            for operacion in operaciones.values():
                respuesta = operacion["responses"].get("422")
                if respuesta is not None and "HTTPValidationError" in str(respuesta):
                    operacion["responses"]["422"] = _ERROR_VALIDACION
        esquema["components"]["schemas"].pop("HTTPValidationError", None)
        esquema["components"]["schemas"].pop("ValidationError", None)
        app.openapi_schema = esquema
    return app.openapi_schema
