from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from src.domain.recomendacion import RegistroRecomendacion
from src.infrastructure.persistence.modelos import RecomendacionLogModelo
from src.infrastructure.persistence.registro_recomendaciones_pg import (
    RegistroRecomendacionesPostgres,
)


def _registro(conversacion_id, turista_id, justificacion="Baja presión de capacidad."):
    return RegistroRecomendacion(
        conversacion_id=conversacion_id,
        turista_id=turista_id,
        servicio_id=uuid4(),
        justificacion=justificacion,
        herramientas_usadas=["buscar_servicios", "presion_capacidad_carga"],
        modelo="proveedor/modelo-1",
        fecha_generacion=datetime(2026, 10, 29, 15, 30, tzinfo=UTC),
    )


async def _filas_de(motor, conversacion_id):
    async with motor.connect() as conexion:
        resultado = await conexion.execute(
            select(RecomendacionLogModelo.__table__).where(
                RecomendacionLogModelo.conversacion_id == conversacion_id
            )
        )
        return {fila.id: fila for fila in resultado}


async def test_registra_y_lee_las_recomendaciones(motor):
    conversacion_id, turista_id = uuid4(), uuid4()
    registros = [_registro(conversacion_id, turista_id), _registro(conversacion_id, turista_id)]

    await RegistroRecomendacionesPostgres(motor).registrar(registros)

    filas = await _filas_de(motor, conversacion_id)
    assert set(filas) == {r.id for r in registros}
    for registro in registros:
        fila = filas[registro.id]
        assert fila.turista_id == turista_id
        assert fila.servicio_id == registro.servicio_id
        assert fila.justificacion == registro.justificacion
        assert fila.herramientas_usadas == registro.herramientas_usadas
        assert fila.modelo == registro.modelo
        assert fila.fecha_generacion == registro.fecha_generacion


async def test_registrar_una_lista_vacia_no_inserta_nada(motor):
    conversacion_id = uuid4()

    await RegistroRecomendacionesPostgres(motor).registrar([])

    assert await _filas_de(motor, conversacion_id) == {}


async def test_si_una_fila_falla_no_se_guarda_ninguna(motor):
    conversacion_id, turista_id = uuid4(), uuid4()
    # La base rechaza justificaciones vacías aunque el dominio no las hubiera filtrado.
    registros = [
        _registro(conversacion_id, turista_id),
        _registro(conversacion_id, turista_id, " "),
    ]

    with pytest.raises(IntegrityError):
        await RegistroRecomendacionesPostgres(motor).registrar(registros)

    assert await _filas_de(motor, conversacion_id) == {}


async def test_la_tabla_no_tiene_columnas_para_el_texto_de_la_conversacion(motor):
    async with motor.connect() as conexion:
        resultado = await conexion.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'recomendacion_log'"
            )
        )
        columnas = {fila.column_name for fila in resultado}

    # Ley 1581: solo qué se recomendó y por qué; ni mensajes ni respuestas del chatbot.
    assert columnas == {
        "id",
        "conversacion_id",
        "turista_id",
        "servicio_id",
        "justificacion",
        "herramientas_usadas",
        "modelo",
        "fecha_generacion",
    }
