"""Regla de capas: el núcleo (domain/ y application/) es Python puro.

* domain/ solo puede importar la librería estándar y a sí mismo.
* application/ solo puede importar la librería estándar, domain/ y a sí mismo.
* Los frameworks y drivers (FastAPI, SQLAlchemy, asyncpg, aio-pika, redis) y la configuración
  (config.py) solo viven en infrastructure/ y main.py; el núcleo los usa a través de los puertos.

Si esta prueba falla, la lógica de negocio quedó amarrada a una librería externa.
"""

import ast
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
ESTANDAR = set(sys.stdlib_module_names)

PERMITIDOS = {
    "domain": ESTANDAR | {"domain"},
    "application": ESTANDAR | {"domain", "application"},
}


def modulos_importados(archivo: Path) -> set[str]:
    """Primer nombre de cada import (`from fastapi.x import y` -> `fastapi`); ignora imports relativos."""
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    nombres: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres |= {alias.name.split(".")[0] for alias in nodo.names}
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            nombres.add(nodo.module.split(".")[0])
    return nombres


@pytest.mark.parametrize("capa", sorted(PERMITIDOS))
def test_la_capa_solo_importa_lo_permitido(capa):
    violaciones = {
        str(archivo.relative_to(SRC)): sorted(prohibidos)
        for archivo in sorted((SRC / capa).rglob("*.py"))
        if (prohibidos := modulos_importados(archivo) - PERMITIDOS[capa])
    }
    assert not violaciones, f"{capa}/ importa módulos no permitidos: {violaciones}"


@pytest.mark.parametrize(
    ("capa", "codigo", "prohibido"),
    [
        ("domain", "from fastapi import FastAPI\nimport datetime\n", {"fastapi"}),
        ("domain", "from application.ports import Reloj\n", {"application"}),  # el dominio no conoce los casos de uso
        ("application", "from infrastructure.persistence.db import crear_motor\n", {"infrastructure"}),
        ("application", "from config import Configuracion\n", {"config"}),
        ("application", "from redis.asyncio import Redis\n", {"redis"}),
    ],
)
def test_la_regla_detecta_cada_violacion(tmp_path, capa, codigo, prohibido):
    """La propia regla funciona: cada import prohibido se detecta."""
    archivo = tmp_path / "ejemplo.py"
    archivo.write_text(codigo, encoding="utf-8")
    assert modulos_importados(archivo) - PERMITIDOS[capa] == prohibido
