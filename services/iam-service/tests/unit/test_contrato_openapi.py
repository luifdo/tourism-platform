"""contracts/openapi/iam.yaml está al día con la app y describe solo la API pública (C-57)."""

from typing import Any

import pytest
import yaml

from scripts.exportar_openapi import CONTRATO, generar

METODOS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return generar()


def _operaciones(esquema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (metodo, ruta, operacion)
        for ruta, operaciones in esquema["paths"].items()
        for metodo, operacion in operaciones.items()
        if metodo in METODOS
    ]


def test_iam_yaml_coincide_con_la_app(esquema: dict[str, Any]) -> None:
    guardado = yaml.safe_load(CONTRATO.read_text(encoding="utf-8"))

    assert guardado == esquema, (
        "contracts/openapi/iam.yaml quedó desactualizado: "
        "ejecuta `uv run python -m scripts.exportar_openapi`."
    )


def test_solo_publica_rutas_bajo_el_prefijo_del_gateway(esquema: dict[str, Any]) -> None:
    fuera = [ruta for ruta in esquema["paths"] if not ruta.startswith("/api/iam/")]

    assert fuera == []  # ni /internal, ni /health, ni /health/live, ni /metrics


def test_los_422_tienen_el_formato_real_del_servicio(esquema: dict[str, Any]) -> None:
    assert "HTTPValidationError" not in esquema["components"]["schemas"]
    assert "HTTPValidationError" not in str(esquema["paths"])


def test_toda_ruta_protegida_declara_token_invalido_y_valkey_caido(esquema: dict[str, Any]) -> None:
    protegidas = [op for op in _operaciones(esquema) if op[2].get("security")]

    assert protegidas
    for metodo, ruta, operacion in protegidas:
        assert {"401", "503"} <= operacion["responses"].keys(), f"{metodo} {ruta}"


@pytest.mark.parametrize("prefijo", ["/api/iam/admin/", "/api/iam/prestador/"])
def test_las_rutas_con_rol_fijo_declaran_el_403(esquema: dict[str, Any], prefijo: str) -> None:
    rutas = [op for op in _operaciones(esquema) if op[1].startswith(prefijo)]

    assert rutas
    for metodo, ruta, operacion in rutas:
        assert "403" in operacion["responses"], f"{metodo} {ruta}"


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("post", "/api/iam/login"),
        ("post", "/api/iam/register"),
        ("post", "/api/iam/auth/restablecer"),
        ("post", "/api/iam/perfil/contrasena"),
        ("delete", "/api/iam/perfil"),
    ],
)
def test_las_rutas_que_calculan_argon2_declaran_servicio_ocupado(
    esquema: dict[str, Any], metodo: str, ruta: str
) -> None:
    assert "SERVICIO_OCUPADO" in esquema["paths"][ruta][metodo]["responses"]["503"]["description"]


def test_los_errores_usan_el_esquema_comun(esquema: dict[str, Any]) -> None:
    for metodo, ruta, operacion in _operaciones(esquema):
        for codigo, respuesta in operacion["responses"].items():
            if codigo.startswith(("4", "5")):
                contenido = respuesta["content"]["application/json"]["schema"]
                assert contenido == {"$ref": "#/components/schemas/ErrorResponse"}, (
                    f"{metodo} {ruta} {codigo}"
                )
