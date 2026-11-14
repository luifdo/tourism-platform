"""Repositorios de booking_db en Postgres (SQLAlchemy Core + asyncpg).

Cada repositorio recibe la conexión (o sesión) de la transacción en curso: la abre y la cierra
`UnidadDeTrabajoPostgres` (al final del archivo), así todo lo que hace un caso de uso se confirma o se deshace junto.
Los repositorios solo traducen filas <-> objetos del dominio; las reglas viven en el dominio.
"""

from datetime import date, datetime
from typing import Self
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from application.errores import DiaExistente, ReservaDuplicada
from application.ports import FiltroReservas
from domain.disponibilidad import DisponibilidadCupo
from domain.eventos import EventoDominio
from domain.reglas import ZONA
from domain.reserva import ESTADOS_ACTIVOS, Actor, EstadoReserva, Reserva
from domain.servicio import ServicioRef
from infrastructure.messaging.sobre import armar_sobre
from infrastructure.persistence.tablas import disponibilidad_cupo, evento_outbox, servicio_ref, solicitud_reserva

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


# ---------- solicitud_reserva ----------

_COLUMNAS_RESERVA = (
    "id", "servicio_id", "turista_id", "prestador_id", "prestador_usuario_id", "fecha_reserva",
    "numero_personas", "estado", "expira_en", "creado_en", "actualizado_en", "motivo", "cancelada_por", "version",
)
_INDICE_R6 = "uq_solicitud_reserva_activa"


def _en_bogota(instante: datetime | None) -> datetime | None:
    # La sesión trabaja en UTC; el dominio y la API muestran la hora de Bogotá (es el mismo instante).
    return instante.astimezone(ZONA) if instante else None


def _reserva(fila: RowMapping) -> Reserva:
    datos = {c: fila[c] for c in _COLUMNAS_RESERVA}
    datos["estado"] = EstadoReserva(datos["estado"])
    datos["cancelada_por"] = Actor(datos["cancelada_por"]) if datos["cancelada_por"] else None
    for c in ("expira_en", "creado_en", "actualizado_en"):
        datos[c] = _en_bogota(datos[c])
    return Reserva(**datos)


class RepositorioReservasPostgres:
    def __init__(self, db: Ejecutor):
        self._db = db

    async def _una(self, consulta: Select) -> Reserva | None:
        fila = (await self._db.execute(consulta)).mappings().first()
        return _reserva(fila) if fila else None

    async def _varias(self, consulta: Select) -> list[Reserva]:
        return [_reserva(f) for f in (await self._db.execute(consulta)).mappings()]

    def _por_id(self, reserva_id: UUID) -> Select:
        return select(solicitud_reserva).where(solicitud_reserva.c.id == reserva_id)

    async def obtener_para_cambiar(self, reserva_id: UUID) -> Reserva | None:
        return await self._una(self._por_id(reserva_id).with_for_update())

    async def leer(self, reserva_id: UUID) -> Reserva | None:
        return await self._una(self._por_id(reserva_id))

    async def guardar(self, reserva: Reserva) -> None:
        """Inserta la reserva nueva o actualiza la existente si su `version` es mayor.

        Igual que con los días: toda transición sube la versión y antes bloqueó la fila, así que
        la condición falla solo si alguien la cambió sin bloquearla (error de programación).
        Si el índice único de R6 la rechaza (otra reserva activa del mismo turista, servicio y
        fecha), se traduce a ReservaDuplicada (409) en vez de un error 500.
        """
        valores = {c: getattr(reserva, c) for c in _COLUMNAS_RESERVA}
        valores["estado"] = reserva.estado.value
        valores["cancelada_por"] = reserva.cancelada_por.value if reserva.cancelada_por else None
        sentencia = insert(solicitud_reserva).values(**valores)
        sentencia = sentencia.on_conflict_do_update(
            index_elements=[solicitud_reserva.c.id],
            set_={c: sentencia.excluded[c] for c in _COLUMNAS_RESERVA if c != "id"},
            where=solicitud_reserva.c.version < sentencia.excluded.version,
        ).returning(solicitud_reserva.c.id)
        try:
            guardada = (await self._db.execute(sentencia)).first()
        except IntegrityError as error:
            if _INDICE_R6 in str(error.orig):
                raise ReservaDuplicada(
                    "Ya tiene una reserva activa para ese servicio y fecha; modifíquela."
                ) from error
            raise
        if guardada is None:
            raise RuntimeError(f"Escritura perdida en la reserva {reserva.id}.")

    async def existe_activa(
        self, turista_id: UUID, servicio_id: UUID, fecha: date, excluir: UUID | None = None
    ) -> bool:
        c = solicitud_reserva.c
        condicion = and_(
            c.turista_id == turista_id, c.servicio_id == servicio_id, c.fecha_reserva == fecha,
            c.estado.in_([e.value for e in ESTADOS_ACTIVOS]),
        )
        if excluir is not None:
            condicion = and_(condicion, c.id != excluir)
        return (await self._db.execute(select(select(c.id).where(condicion).exists()))).scalar_one()

    async def listar(self, filtro: FiltroReservas, pagina: int, tamano: int) -> tuple[list[Reserva], int]:
        """Una página y el total de coincidencias en la misma consulta (`COUNT(*) OVER ()`)."""
        c = solicitud_reserva.c
        condiciones = [
            columna == valor
            for columna, valor in (
                (c.turista_id, filtro.turista_id),
                (c.prestador_usuario_id, filtro.prestador_usuario_id),
                (c.servicio_id, filtro.servicio_id),
                (c.estado, filtro.estado.value if filtro.estado else None),
            )
            if valor is not None
        ]
        if filtro.desde is not None:
            condiciones.append(c.fecha_reserva >= filtro.desde)
        if filtro.hasta is not None:
            condiciones.append(c.fecha_reserva <= filtro.hasta)
        if filtro.orden == "expira_en":  # panel del prestador: lo más urgente primero
            orden = (c.expira_en.asc().nulls_last(), c.creado_en.asc(), c.id)
        else:  # historial: lo más reciente primero
            orden = (c.creado_en.desc(), c.id)
        consulta = (
            select(solicitud_reserva, func.count().over().label("total"))
            .where(*condiciones)
            .order_by(*orden)  # `id` desempata: la paginación no repite ni salta filas
            .limit(tamano)
            .offset((pagina - 1) * tamano)
        )
        filas = (await self._db.execute(consulta)).mappings().all()
        if filas:
            return [_reserva(f) for f in filas], filas[0]["total"]
        # Página vacía (p. ej. más allá de la última): el total sale de un conteo aparte.
        conteo = select(func.count()).select_from(solicitud_reserva).where(*condiciones)
        return [], (await self._db.execute(conteo)).scalar_one()

    async def solicitudes_vencidas(self, ahora: datetime, limite: int) -> list[Reserva]:
        """FOR UPDATE SKIP LOCKED: si corren dos CronJobs a la vez, cada uno toma reservas
        distintas y ninguno espera al otro. Las que estaban bloqueadas se toman en la próxima corrida."""
        c = solicitud_reserva.c
        return await self._varias(
            select(solicitud_reserva)
            .where(c.estado == EstadoReserva.SOLICITADA.value, c.expira_en <= ahora)
            .order_by(c.expira_en)
            .limit(limite)
            .with_for_update(skip_locked=True)
        )

    async def por_finalizar(self, hoy: date, limite: int) -> list[Reserva]:
        c = solicitud_reserva.c
        return await self._varias(
            select(solicitud_reserva)
            .where(c.estado == EstadoReserva.CONFIRMADA.value, c.fecha_reserva < hoy)
            .order_by(c.fecha_reserva)
            .limit(limite)
            .with_for_update(skip_locked=True)
        )


# ---------- evento_outbox ----------

class OutboxPostgres:
    def __init__(self, db: Ejecutor):
        self._db = db

    async def agregar(self, eventos: list[EventoDominio], correlation_id: str | None) -> None:
        """Un INSERT por evento en evento_outbox, dentro de la transacción del caso de uso.

        La fila guarda el sobre completo (envelope.v1.json) y su `id` es el `event_id`: si el
        relay lo publica dos veces (se cayó tras publicar y antes de marcarlo), los
        consumidores lo descartan por ese id. `publicado_en` nulo = pendiente.
        `clock_timestamp()` (y no `now()`, que es fijo en toda la transacción) da a cada evento
        su propio instante, así el relay los publica en el orden en que se produjeron.
        """
        if not eventos:
            return
        sobres = [armar_sobre(e, correlation_id) for e in eventos]
        await self._db.execute(
            insert(evento_outbox).values(creado_en=func.clock_timestamp()),
            [{"id": UUID(s["event_id"]), "tipo": s["event_type"], "sobre": s} for s in sobres],
        )


# ---------- Unidad de trabajo ----------

class UnidadDeTrabajoPostgres:
    """Una transacción de booking_db por caso de uso.

    Al entrar toma una conexión del pool y abre la transacción; los tres repositorios
    trabajan sobre esa misma sesión. `commit()` confirma. Al salir, lo no confirmado se
    deshace (ROLLBACK, también si hubo una excepción) y la conexión vuelve al pool.
    """

    def __init__(self, sesiones: async_sessionmaker[AsyncSession]):
        self._sesiones = sesiones

    async def __aenter__(self) -> Self:
        self._sesion = self._sesiones()
        await self._sesion.begin()
        self.servicios = RepositorioServiciosPostgres(self._sesion)
        self.reservas = RepositorioReservasPostgres(self._sesion)
        self.disponibilidad = RepositorioDisponibilidadPostgres(self._sesion)
        self.outbox = OutboxPostgres(self._sesion)
        return self

    async def __aexit__(self, *exc: object) -> None:
        try:
            if self._sesion.in_transaction():
                await self._sesion.rollback()
        finally:
            await self._sesion.close()

    async def commit(self) -> None:
        await self._sesion.commit()


def fabrica_postgres(sesiones: async_sessionmaker[AsyncSession]):
    return lambda: UnidadDeTrabajoPostgres(sesiones)
