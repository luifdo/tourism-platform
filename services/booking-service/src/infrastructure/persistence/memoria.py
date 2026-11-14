"""Persistencia en memoria: para pruebas y para la demo sin Postgres.

Imita lo que garantiza Postgres en lo que importa a la aplicación:
* una transacción a la vez (un candado global hace el papel de `FOR UPDATE`);
* lo leído es una copia: si no hay `commit`, nada cambia (rollback);
* las restricciones únicas de `solicitud_reserva` y `disponibilidad_cupo`;
* el outbox: los eventos se entregan al publicador solo si hay COMMIT.
"""

import asyncio
import copy
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Self
from uuid import UUID

from application.ports import FiltroReservas
from domain.disponibilidad import DisponibilidadCupo
from domain.eventos import EventoDominio
from domain.reserva import ESTADOS_ACTIVOS, EstadoReserva, Reserva
from domain.servicio import ServicioRef
from infrastructure.messaging.memoria import PublicadorMemoria
from infrastructure.messaging.sobre import armar_sobre


@dataclass
class AlmacenMemoria:
    servicios: dict[UUID, ServicioRef] = field(default_factory=dict)
    reservas: dict[UUID, Reserva] = field(default_factory=dict)
    dias: dict[tuple[UUID, date], DisponibilidadCupo] = field(default_factory=dict)
    candado: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Qué filas se pidieron "para cambiar" (en Postgres serían FOR UPDATE). Lo revisan las pruebas.
    bloqueos: list[tuple[str, object]] = field(default_factory=list)


class _Cambios:
    def __init__(self) -> None:
        self.servicios: dict[UUID, ServicioRef] = {}
        self.reservas: dict[UUID, Reserva] = {}
        self.dias: dict[tuple[UUID, date], DisponibilidadCupo] = {}
        self.sobres: list[dict[str, Any]] = []


class RepositorioServiciosMemoria:
    def __init__(self, almacen: AlmacenMemoria, cambios: _Cambios):
        self._a, self._c = almacen, cambios

    async def leer(self, servicio_id: UUID) -> ServicioRef | None:
        s = self._c.servicios.get(servicio_id) or self._a.servicios.get(servicio_id)
        return copy.deepcopy(s)

    async def guardar_si_mas_nuevo(self, servicio: ServicioRef) -> bool:
        # Aquí leer y comparar es seguro: el candado global no deja correr otra transacción.
        if not servicio.reemplaza_a(await self.leer(servicio.servicio_id)):
            return False
        self._c.servicios[servicio.servicio_id] = copy.deepcopy(servicio)
        return True


class RepositorioDisponibilidadMemoria:
    def __init__(self, almacen: AlmacenMemoria, cambios: _Cambios):
        self._a, self._c = almacen, cambios

    def _todos(self) -> dict[tuple[UUID, date], DisponibilidadCupo]:
        return {**self._a.dias, **self._c.dias}

    async def obtener_para_cambiar(self, servicio_id: UUID, fecha: date) -> DisponibilidadCupo | None:
        self._a.bloqueos.append(("dia", (servicio_id, fecha)))
        return copy.deepcopy(self._todos().get((servicio_id, fecha)))

    async def guardar(self, dia: DisponibilidadCupo) -> None:
        if not 0 <= dia.cupos_disponibles <= dia.cupos_totales:  # CHECK de la tabla
            raise ValueError("cupos_disponibles fuera de rango")
        self._c.dias[(dia.servicio_id, dia.fecha)] = copy.deepcopy(dia)

    async def rango(self, servicio_id: UUID, desde: date, hasta: date) -> list[DisponibilidadCupo]:
        dias = [d for (sid, f), d in self._todos().items() if sid == servicio_id and desde <= f <= hasta]
        return copy.deepcopy(sorted(dias, key=lambda d: d.fecha))


class RepositorioReservasMemoria:
    def __init__(self, almacen: AlmacenMemoria, cambios: _Cambios):
        self._a, self._c = almacen, cambios

    def _todas(self) -> list[Reserva]:
        return list({**self._a.reservas, **self._c.reservas}.values())

    async def obtener_para_cambiar(self, reserva_id: UUID) -> Reserva | None:
        self._a.bloqueos.append(("reserva", reserva_id))
        return await self.leer(reserva_id)

    async def leer(self, reserva_id: UUID) -> Reserva | None:
        r = self._c.reservas.get(reserva_id) or self._a.reservas.get(reserva_id)
        return copy.deepcopy(r)

    async def guardar(self, reserva: Reserva) -> None:
        guardada = copy.deepcopy(reserva)
        guardada.eventos = []
        self._c.reservas[reserva.id] = guardada

    async def existe_activa(
        self, turista_id: UUID, servicio_id: UUID, fecha: date, excluir: UUID | None = None
    ) -> bool:
        return any(
            r.turista_id == turista_id and r.servicio_id == servicio_id and r.fecha_reserva == fecha
            and r.estado in ESTADOS_ACTIVOS and r.id != excluir
            for r in self._todas()
        )

    async def listar(self, filtro: FiltroReservas, pagina: int, tamano: int) -> tuple[list[Reserva], int]:
        def coincide(r: Reserva) -> bool:
            return (
                (filtro.turista_id is None or r.turista_id == filtro.turista_id)
                and (filtro.prestador_usuario_id is None or r.prestador_usuario_id == filtro.prestador_usuario_id)
                and (filtro.servicio_id is None or r.servicio_id == filtro.servicio_id)
                and (filtro.estado is None or r.estado is filtro.estado)
                and (filtro.desde is None or r.fecha_reserva >= filtro.desde)
                and (filtro.hasta is None or r.fecha_reserva <= filtro.hasta)
            )

        encontradas = [r for r in self._todas() if coincide(r)]
        if filtro.orden == "expira_en":
            encontradas.sort(key=lambda r: (r.expira_en is None, r.expira_en or r.creado_en))
        else:
            encontradas.sort(key=lambda r: r.creado_en, reverse=True)
        inicio = (pagina - 1) * tamano
        return copy.deepcopy(encontradas[inicio : inicio + tamano]), len(encontradas)

    async def solicitudes_vencidas(self, ahora: datetime, limite: int) -> list[Reserva]:
        vencidas = [
            r for r in self._todas()
            if r.estado is EstadoReserva.SOLICITADA and r.expira_en is not None and r.expira_en <= ahora
        ]
        return copy.deepcopy(sorted(vencidas, key=lambda r: r.expira_en)[:limite])

    async def por_finalizar(self, hoy: date, limite: int) -> list[Reserva]:
        pasadas = [r for r in self._todas() if r.estado is EstadoReserva.CONFIRMADA and r.fecha_reserva < hoy]
        return copy.deepcopy(sorted(pasadas, key=lambda r: r.fecha_reserva)[:limite])


class OutboxMemoria:
    def __init__(self, cambios: _Cambios):
        self._c = cambios

    async def agregar(self, eventos: list[EventoDominio], correlation_id: str | None) -> None:
        self._c.sobres.extend(armar_sobre(e, correlation_id) for e in eventos)


class UnidadDeTrabajoMemoria:
    def __init__(self, almacen: AlmacenMemoria, publicador: PublicadorMemoria):
        self._almacen = almacen
        self._publicador = publicador

    async def __aenter__(self) -> Self:
        await self._almacen.candado.acquire()
        self._cambios = _Cambios()
        self.servicios = RepositorioServiciosMemoria(self._almacen, self._cambios)
        self.reservas = RepositorioReservasMemoria(self._almacen, self._cambios)
        self.disponibilidad = RepositorioDisponibilidadMemoria(self._almacen, self._cambios)
        self.outbox = OutboxMemoria(self._cambios)
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._cambios = _Cambios()  # lo no confirmado se descarta
        self._almacen.candado.release()

    async def commit(self) -> None:
        self._almacen.servicios.update(self._cambios.servicios)
        self._almacen.dias.update(self._cambios.dias)
        self._almacen.reservas.update(self._cambios.reservas)
        # Sin relay en memoria: lo que en Postgres queda en evento_outbox se entrega aquí mismo.
        await self._publicador.publicar(self._cambios.sobres)
        self._cambios = _Cambios()
        # Los repositorios siguen leyendo del almacén ya actualizado.
        self.servicios._c = self.reservas._c = self.disponibilidad._c = self.outbox._c = self._cambios


def fabrica_memoria(almacen: AlmacenMemoria, publicador: PublicadorMemoria):
    return lambda: UnidadDeTrabajoMemoria(almacen, publicador)
