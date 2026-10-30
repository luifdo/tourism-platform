"""EnviadorSmtp sin servidor: un fallo se traduce sin revelar el destinatario (C-50)."""

import time

import pytest

from app.domain.exceptions import ServicioNoDisponibleError
from app.domain.ports.enviador_correo import Correo
from app.infrastructure.correo.enviador_smtp import EnviadorSmtp
from tests.fakes import ServidorMudo

CORREO = Correo(destinatario="maria@example.com", asunto="A", texto="enlace", html="<p>x</p>")


async def test_smtp_caido_es_servicio_no_disponible_sin_el_correo_en_el_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    enviador = EnviadorSmtp(
        host="127.0.0.1",
        puerto=1,
        remitente="no-responder@example.com",
        usuario=None,
        clave=None,
        starttls=False,
        timeout_segundos=1,
    )

    with pytest.raises(ServicioNoDisponibleError):
        await enviador.enviar(CORREO)

    assert "maria@example.com" not in caplog.text


async def test_smtp_que_no_responde_respeta_el_timeout() -> None:
    with ServidorMudo() as mudo:
        enviador = EnviadorSmtp(
            host="127.0.0.1",
            puerto=mudo.puerto,
            remitente="no-responder@example.com",
            usuario=None,
            clave=None,
            starttls=False,
            timeout_segundos=0.3,
        )
        inicio = time.monotonic()

        with pytest.raises(ServicioNoDisponibleError):
            await enviador.enviar(CORREO)

    assert time.monotonic() - inicio < 2


def test_el_repr_del_correo_no_muestra_datos() -> None:
    assert "maria@example.com" not in repr(CORREO)
    assert "enlace" not in repr(CORREO)
