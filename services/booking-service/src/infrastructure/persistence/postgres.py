"""Repositorios de booking_db en Postgres (SQLAlchemy Core + asyncpg).

Cada repositorio recibe la conexión (o sesión) de la transacción en curso: la abre y la cierra
la unidad de trabajo (paso 5.2e), así todo lo que hace un caso de uso se confirma o se deshace junto.
Los repositorios solo traducen filas <-> objetos del dominio; las reglas viven en el dominio.
"""

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from application.errores import DiaExistente
from domain.disponibilidad import DisponibilidadCupo
from domain.servicio import ServicioRef
from infrastructure.persistence.tablas import disponibilidad_cupo, servicio_ref

Ejecutor = AsyncConnection | AsyncSession  # ambos tienen `execute`; las pruebas usan una conexión


# ---------- servicio_ref ----------

_COLUMNAS_SERVICIO = (
    "servicio_id", "prestador_id", "prestador_usuario_id",
    "capacidad_aforo_diario", "tarifa_base", "activo", "version",
)


def _servicio(fila: RowMapping) -> ServicioRef:
    return ServicioRef(**{c: fila[c] for c in _COLUMNAS_SERVICIO})


class RepositorioServiciosPostgres:
    def __init__(self, db: Ejecutor):
        self._db = db

    async def leer(self, servicio_id: UUID) -> ServicioRef | None:
        fila = (await self._db.execute(
            select(servicio_ref).where(servicio_ref.c.servicio_id == servicio_id)
        )).mappings().first()
        return _servicio(fila) if fila else None

    async def guardar_si_mas_nuevo(self, servicio: ServicioRef) -> bool:
        """Una sola sentencia, sin leer antes:

            INSERT ... ON CONFLICT (servicio_id) DO UPDATE SET ...
            WHERE servicio_ref.version < EXCLUDED.version
            RETURNING servicio_id

        * Si el servicio no existe, lo inserta.
        * Si existe, lo reemplaza solo si la versión que llega es mayor (la misma regla que
          `ServicioRef.reemplaza_a`). Si no, no toca nada y `RETURNING` no devuelve fila.
        * Si dos réplicas reciben dos eventos del mismo servicio a la vez, Postgres hace esperar
          a la segunda hasta que la primera confirme y compara contra lo ya guardado: siempre
          queda la versión mayor. Con "leer, comparar y guardar" podía ganar la menor.
        """
        valores = {c: getattr(servicio, c) for c in _COLUMNAS_SERVICIO}
        sentencia = insert(servicio_ref).values(**valores)
        sentencia = sentencia.on_conflict_do_update(
            index_elements=[servicio_ref.c.servicio_id],
            set_={
                **{c: sentencia.excluded[c] for c in _COLUMNAS_SERVICIO if c != "servicio_id"},
                "actualizado_en": func.now(),
            },
            where=servicio_ref.c.version < sentencia.excluded.version,
        ).returning(servicio_ref.c.servicio_id)
        return (await self._db.execute(sentencia)).first() is not None


# ---------- disponibilidad_cupo ----------

_COLUMNAS_DIA = (
    "servicio_id", "fecha", "cupos_totales", "cupos_disponibles", "tarifa_dia", "version", "secuencia",
)


def _dia(fila: RowMapping) -> DisponibilidadCupo:
    return DisponibilidadCupo(**{c: fila[c] for c in _COLUMNAS_DIA})


class RepositorioDisponibilidadPostgres:
    def __init__(self, db: Ejecutor):
        self._db = db

    def _del_servicio(self, servicio_id: UUID):
        return select(disponibilidad_cupo).where(disponibilidad_cupo.c.servicio_id == servicio_id)

    async def obtener_para_cambiar(self, servicio_id: UUID, fecha: date) -> DisponibilidadCupo | None:
        """SELECT ... FOR UPDATE: la fila queda bloqueada hasta el COMMIT o ROLLBACK.

        Si otra transacción ya la tiene, esta espera, y al seguir lee el valor ya confirmado.
        Así dos turistas no toman a la vez el último cupo: el segundo ve que ya no queda.
        """
        fila = (await self._db.execute(
            self._del_servicio(servicio_id).where(disponibilidad_cupo.c.fecha == fecha).with_for_update()
        )).mappings().first()
        return _dia(fila) if fila else None

    async def guardar(self, dia: DisponibilidadCupo) -> None:
        """Inserta el día, o lo actualiza si ya existe, solo si su `secuencia` es mayor que la guardada.

        Toda modificación sube `secuencia` y antes bloqueó la fila con `obtener_para_cambiar`, así
        que para un día existente la condición siempre se cumple. Solo falla en un caso real: un día
        **nuevo** no tiene fila que bloquear, y si dos peticiones lo crean a la vez las dos llegan
        con secuencia 1. La segunda espera a la primera, ve el día ya creado y no lo pisa.
        """
        valores = {c: getattr(dia, c) for c in _COLUMNAS_DIA}
        sentencia = insert(disponibilidad_cupo).values(**valores)
        sentencia = sentencia.on_conflict_do_update(
            index_elements=[disponibilidad_cupo.c.servicio_id, disponibilidad_cupo.c.fecha],
            set_={
                **{c: sentencia.excluded[c] for c in _COLUMNAS_DIA if c not in ("servicio_id", "fecha")},
                "actualizado_en": func.now(),
            },
            where=disponibilidad_cupo.c.secuencia < sentencia.excluded.secuencia,
        ).returning(disponibilidad_cupo.c.fecha)
        if (await self._db.execute(sentencia)).first() is None:
            if dia.secuencia == 1:
                raise DiaExistente(f"El día {dia.fecha.isoformat()} ya fue creado por otra petición.")
            # Un día existente que se guarda sin haberlo bloqueado: error de programación, no del usuario.
            raise RuntimeError(f"Escritura perdida en disponibilidad {dia.servicio_id} {dia.fecha}.")

    async def rango(self, servicio_id: UUID, desde: date, hasta: date) -> list[DisponibilidadCupo]:
        filas = (await self._db.execute(
            self._del_servicio(servicio_id)
            .where(disponibilidad_cupo.c.fecha.between(desde, hasta))
            .order_by(disponibilidad_cupo.c.fecha)
        )).mappings()
        return [_dia(f) for f in filas]
