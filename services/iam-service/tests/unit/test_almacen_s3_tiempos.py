"""AlmacenDocumentosS3 sin SeaweedFS: tiempos, tope total e hilos propios (C-59)."""

import asyncio
import logging
import threading
import time
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest

from app.domain.exceptions import ServicioNoDisponibleError
from app.infrastructure.observabilidad.contexto_correlacion import (
    correlation_id_actual,
    fijar_correlation_id,
)
from app.infrastructure.storage import almacen_documentos_s3
from app.infrastructure.storage.almacen_documentos_s3 import AlmacenDocumentosS3
from tests.fakes import ServidorMudo


@pytest.fixture
def servidor() -> Iterator[ServidorMudo]:
    with ServidorMudo() as mudo:
        yield mudo


def _almacen(url: str, tope: float = 0.5, hilos: int = 2) -> AlmacenDocumentosS3:
    return AlmacenDocumentosS3(
        endpoint_interno=url,
        endpoint_publico=url,
        region="us-east-1",
        access_key="x",
        secret_key="y",
        bucket="b",
        hilos_maximos=hilos,
        tiempo_maximo_segundos=tope,
    )


def test_configuracion_de_boto3() -> None:
    config = _almacen("http://127.0.0.1:1")._interno.meta.config

    assert (config.connect_timeout, config.read_timeout) == (2, 5)
    assert config.retries["mode"] == "standard"
    # botocore guarda max_attempts=2 como 3 intentos en total: por eso hace falta el tope.
    assert config.retries["total_max_attempts"] == 3


async def test_guardar_respeta_el_tope_total(servidor: ServidorMudo) -> None:
    almacen = _almacen(servidor.url)
    inicio = time.monotonic()

    with pytest.raises(ServicioNoDisponibleError):
        await almacen.guardar("a/b.pdf", b"%PDF-", "application/pdf")

    assert time.monotonic() - inicio < 2
    almacen.cerrar()


async def test_borrar_prefijo_respeta_el_tope_total(
    servidor: ServidorMudo, caplog: pytest.LogCaptureFixture
) -> None:
    almacen = _almacen(servidor.url)
    inicio = time.monotonic()

    with caplog.at_level(logging.ERROR), pytest.raises(ServicioNoDisponibleError):
        await almacen.borrar_prefijo("a/")

    assert time.monotonic() - inicio < 2
    assert "SeaweedFS no borró los documentos: TimeoutError" in caplog.text
    almacen.cerrar()


async def test_el_cliente_se_crea_en_un_hilo_de_s3_una_sola_vez(servidor: ServidorMudo) -> None:
    almacen = _almacen(servidor.url, tope=0.2)
    creados: list[str] = []
    crear = almacen_documentos_s3._cliente

    def contar(*args: Any) -> Any:
        creados.append(threading.current_thread().name)
        return crear(*args)

    with patch.object(almacen_documentos_s3, "_cliente", contar):
        await asyncio.gather(
            almacen.guardar("a/1.pdf", b"%PDF-", "application/pdf"),
            almacen.guardar("a/2.pdf", b"%PDF-", "application/pdf"),
            return_exceptions=True,
        )
        almacen._hilos.shutdown(wait=False, cancel_futures=True)
        await asyncio.to_thread(lambda: almacen._creando_interno.acquire(timeout=5))

    assert len(creados) == 1
    assert creados[0].startswith("s3")


async def test_lo_que_espera_un_hilo_libre_no_corre_despues_del_tope() -> None:
    almacen = _almacen("http://127.0.0.1:1", tope=0.2, hilos=1)
    soltar = threading.Event()
    corrio: list[bool] = []

    ocupado = almacen._en_hilo(soltar.wait, 5)
    with pytest.raises(TimeoutError):
        await ocupado
    with pytest.raises(TimeoutError):
        await almacen._en_hilo(lambda: corrio.append(True))
    soltar.set()
    almacen._hilos.shutdown(wait=True)

    assert corrio == []


async def test_corre_en_hilos_propios_con_el_correlation_id() -> None:
    almacen = _almacen("http://127.0.0.1:1", tope=5)
    fijar_correlation_id("corr-s3")

    nombre = await almacen._en_hilo(lambda: threading.current_thread().name)
    correlacion = await almacen._en_hilo(correlation_id_actual)

    assert nombre.startswith("s3")
    assert correlacion == "corr-s3"
    almacen.cerrar()
