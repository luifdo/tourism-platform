"""Los logs salen en JSON, una línea por registro, con el correlation_id de la petición."""

import json
import logging
import sys

from infrastructure.observabilidad.correlacion import fijar_correlation_id
from infrastructure.observabilidad.logs import FormateadorJson


def _registro(mensaje: str, exc_info=None) -> logging.LogRecord:
    return logging.LogRecord("booking.prueba", logging.WARNING, __file__, 1, mensaje, None, exc_info)


def test_formato_json_con_correlation_id():
    fijar_correlation_id("corr-log-1")
    linea = FormateadorJson("booking-service").format(_registro("Cupos insuficientes"))
    registro = json.loads(linea)
    assert registro["servicio"] == "booking-service"
    assert registro["nivel"] == "WARNING"
    assert registro["logger"] == "booking.prueba"
    assert registro["mensaje"] == "Cupos insuficientes"
    assert registro["correlation_id"] == "corr-log-1"
    assert "ts" in registro and "\n" not in linea


def test_incluye_la_excepcion():
    try:
        raise ValueError("falló")
    except ValueError:
        linea = FormateadorJson("booking-service").format(_registro("error", sys.exc_info()))
    assert "ValueError: falló" in json.loads(linea)["excepcion"]
