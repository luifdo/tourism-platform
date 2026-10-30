"""Punto de entrada de los CronJobs: argumentos y modo de persistencia."""

import pytest

import cron
from config import Configuracion


def test_las_tareas_se_llaman_como_los_cronjobs():
    assert sorted(cron.TAREAS) == ["expirar-solicitudes", "finalizar-reservas"]


def test_en_modo_memoria_no_corre_y_sale_con_2():
    # Un proceso aparte no ve las reservas en memoria de la API: correr ahí no tendría efecto.
    assert cron.main(["expirar-solicitudes"], Configuracion(modo_persistencia="memoria")) == 2


def test_tarea_desconocida_la_rechaza_argparse():
    with pytest.raises(SystemExit) as salida:
        cron.main(["borrar-todo"], Configuracion(modo_persistencia="memoria"))
    assert salida.value.code == 2
