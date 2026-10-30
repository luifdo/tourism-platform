import json
import logging

from app.infrastructure.observabilidad.contexto_correlacion import fijar_correlation_id
from app.infrastructure.observabilidad.formateador_json import FormateadorJson


def registro(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord("app.prueba", logging.INFO, __file__, 1, "hola", None, None)
    for clave, valor in extra.items():
        setattr(record, clave, valor)
    return record


def test_una_linea_json_con_correlation_id() -> None:
    fijar_correlation_id("corr-log-1")

    linea = FormateadorJson("iam-service").format(registro())

    datos = json.loads(linea)
    assert "\n" not in linea
    assert (datos["servicio"], datos["nivel"], datos["mensaje"]) == ("iam-service", "INFO", "hola")
    assert datos["correlation_id"] == "corr-log-1"


def test_campos_estructurados_sin_pisar_las_claves_fijas() -> None:
    fijar_correlation_id("corr-log-2")
    campos = {"usuario_id": "u-1", "resultado": "ok", "correlation_id": "falso"}

    datos = json.loads(FormateadorJson("iam-service").format(registro(campos=campos)))

    assert (datos["usuario_id"], datos["resultado"]) == ("u-1", "ok")
    assert datos["correlation_id"] == "corr-log-2"
