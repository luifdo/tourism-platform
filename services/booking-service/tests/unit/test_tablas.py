"""Paso 5.1b: las tablas definidas coinciden con el modelo de booking_db (sin conectarse a Postgres).

La prueba contra un Postgres real llega en el paso 5.1c, con la migración.
"""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from domain.reserva import EstadoReserva
from infrastructure.persistence.tablas import (
    disponibilidad_cupo,
    evento_outbox,
    metadata,
    servicio_ref,
    solicitud_reserva,
)


def checks(tabla) -> dict[str, str]:
    return {c.name: str(c.sqltext) for c in tabla.constraints if isinstance(c, CheckConstraint)}


def indices(tabla) -> dict:
    return {i.name: i for i in tabla.indexes}


def sql(elemento) -> str:
    """El SQL que se ejecutaría en Postgres."""
    return str(elemento.compile(dialect=postgresql.dialect()))


def test_son_las_cuatro_tablas_del_modelo():
    assert set(metadata.tables) == {"servicio_ref", "disponibilidad_cupo", "solicitud_reserva", "evento_outbox"}


def test_el_dinero_es_numeric_y_las_horas_timestamptz():
    for tabla, columna in [(servicio_ref, "tarifa_base"), (disponibilidad_cupo, "tarifa_dia")]:
        tipo = tabla.c[columna].type
        assert isinstance(tipo, Numeric) and (tipo.precision, tipo.scale) == (12, 2)
    for tabla, columna in [(solicitud_reserva, "expira_en"), (solicitud_reserva, "creado_en"), (evento_outbox, "publicado_en")]:
        assert tabla.c[columna].type.timezone is True


class TestServicioRef:
    def test_lleva_los_dos_ids_del_prestador(self):
        assert {"prestador_id", "prestador_usuario_id"} <= set(servicio_ref.c.keys())
        assert [c.name for c in servicio_ref.primary_key] == ["servicio_id"]

    def test_restricciones(self):
        assert set(checks(servicio_ref).values()) == {"capacidad_aforo_diario >= 1", "tarifa_base >= 0", "version >= 1"}
        assert "ix_servicio_ref_prestador_usuario_id" in indices(servicio_ref)


class TestDisponibilidadCupo:
    def test_la_llave_es_el_servicio_y_el_dia(self):
        assert [c.name for c in disponibilidad_cupo.primary_key] == ["servicio_id", "fecha"]

    def test_solo_se_abren_dias_de_servicios_conocidos(self):
        [fk] = disponibilidad_cupo.c.servicio_id.foreign_keys
        assert fk.target_fullname == "servicio_ref.servicio_id"

    def test_el_check_contra_la_sobreventa(self):
        assert checks(disponibilidad_cupo)["ck_disponibilidad_cupo_disponibles_en_rango"] == (
            "cupos_disponibles BETWEEN 0 AND cupos_totales"
        )

    def test_tiene_los_dos_contadores(self):
        assert {"version", "secuencia"} <= set(disponibilidad_cupo.c.keys())


class TestSolicitudReserva:
    def test_apunta_al_dia_reservado_con_una_llave_compuesta(self):
        [fk] = [c for c in solicitud_reserva.constraints if isinstance(c, ForeignKeyConstraint)]
        assert fk.column_keys == ["servicio_id", "fecha_reserva"]
        assert [e.target_fullname for e in fk.elements] == ["disponibilidad_cupo.servicio_id", "disponibilidad_cupo.fecha"]

    def test_los_estados_permitidos_son_exactamente_los_del_dominio(self):
        texto = checks(solicitud_reserva)["ck_solicitud_reserva_estado_valido"]
        assert all(f"'{e.value}'" in texto for e in EstadoReserva)
        assert texto.count("'") == 2 * len(EstadoReserva)

    def test_coherencia_entre_estado_plazo_motivo_y_quien_cancela(self):
        assert {
            "ck_solicitud_reserva_plazo_solo_en_solicitada",
            "ck_solicitud_reserva_rechazo_con_motivo",
            "ck_solicitud_reserva_cancelada_por_solo_en_cancelada",
            "ck_solicitud_reserva_cancelada_por_valido",
        } <= set(checks(solicitud_reserva))

    def test_r6_una_sola_reserva_activa_por_turista_servicio_y_fecha(self):
        indice = indices(solicitud_reserva)["uq_solicitud_reserva_activa"]
        assert indice.unique
        assert sql(CreateIndex(indice)) == (
            "CREATE UNIQUE INDEX uq_solicitud_reserva_activa ON solicitud_reserva "
            "(turista_id, servicio_id, fecha_reserva) WHERE estado IN ('SOLICITADA', 'CONFIRMADA')"
        )

    def test_indices_para_historial_panel_y_cronjobs(self):
        assert {
            "ix_solicitud_reserva_historial",
            "ix_solicitud_reserva_panel",
            "ix_solicitud_reserva_por_expirar",
            "ix_solicitud_reserva_por_finalizar",
        } <= set(indices(solicitud_reserva))


class TestEventoOutbox:
    def test_columnas_e_indice_de_pendientes(self):
        assert {"id", "tipo", "sobre", "publicado_en", "intentos", "ultimo_error"} <= set(evento_outbox.c.keys())
        assert isinstance(evento_outbox.c.sobre.type, postgresql.JSONB)
        assert "WHERE publicado_en IS NULL" in sql(CreateIndex(indices(evento_outbox)["ix_evento_outbox_pendientes"]))


def test_el_ddl_de_postgres_se_genera_sin_errores():
    """Imprime el CREATE TABLE real (se ve con `pytest -s`)."""
    for tabla in metadata.sorted_tables:
        ddl = sql(CreateTable(tabla))
        assert ddl.startswith(f"\nCREATE TABLE {tabla.name}")
        print(ddl)
