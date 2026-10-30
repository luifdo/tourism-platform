"""El código no puede exponer rutas que el contrato acordado no declara."""

from pathlib import Path

import yaml

from src.main import app

CONTRATO = Path(__file__).parents[4] / "contracts" / "openapi" / "recommendation.yaml"
PREFIJO = "/api/recommendations"


def _rutas_del_contrato() -> set[tuple[str, str]]:
    contrato = yaml.safe_load(CONTRATO.read_text(encoding="utf-8"))
    rutas = set()
    for ruta, operaciones in contrato["paths"].items():
        for metodo, detalle in operaciones.items():
            # `/health` y `/metrics` declaran `servers: [/]`, así que van sin prefijo.
            sin_prefijo = detalle.get("servers") == [{"url": "/"}]
            completa = ruta if sin_prefijo else PREFIJO + ruta
            rutas.add((metodo.upper(), completa))
    return rutas


def _rutas_del_codigo() -> set[tuple[str, str]]:
    esquema = app.openapi()["paths"]
    return {(m.upper(), r) for r, ops in esquema.items() for m in ops}


def test_toda_ruta_del_codigo_esta_en_el_contrato():
    sobrantes = _rutas_del_codigo() - _rutas_del_contrato()

    assert not sobrantes, f"Rutas que el contrato no declara: {sobrantes}"
