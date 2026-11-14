"""Cupos de un servicio en un día (Guía §4.4). El dueño sale de `ServicioRef`.

La fila lleva dos contadores, con propósitos distintos:

* `version`: solo sube cuando el prestador edita totales o tarifa. Es la del `ETag`/`If-Match`;
  así una reserva ajena no causa un conflicto falso cuando la PWA sincroniza una edición
  hecha sin conexión (ESC-09).
* `secuencia`: sube con **cada** cambio de la fila (reservas y ediciones). Es la que viaja como
  `version` en el evento `disponibilidad.actualizada`, porque catalog descarta los eventos con
  un número menor o igual al que ya tiene y necesita ver también los cambios por reservas.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from domain.errores import CuposComprometidos, CuposInsuficientes, SuperaAforo, Validacion
from domain.eventos import EventoDominio


@dataclass
class DisponibilidadCupo:
    servicio_id: UUID
    fecha: date
    cupos_totales: int
    cupos_disponibles: int
    tarifa_dia: Decimal | None = None
    version: int = 1  # ediciones del prestador (ETag / If-Match)
    secuencia: int = 1  # cualquier cambio de la fila (evento disponibilidad.actualizada)

    @classmethod
    def abrir(
        cls,
        servicio_id: UUID,
        fecha: date,
        cupos_totales: int,
        tarifa_dia: Decimal | None = None,
        aforo: int | None = None,
    ) -> "DisponibilidadCupo":
        _validar_totales(cupos_totales, tarifa_dia, aforo)
        return cls(servicio_id, fecha, cupos_totales, cupos_totales, tarifa_dia)

    @property
    def cupos_reservados(self) -> int:
        return self.cupos_totales - self.cupos_disponibles

    def descontar(self, personas: int) -> None:
        if personas < 1:
            raise Validacion("El número de personas debe ser al menos 1.")
        if personas > self.cupos_disponibles:
            raise CuposInsuficientes(
                f"Solo quedan {self.cupos_disponibles} cupos para el {self.fecha.isoformat()}."
            )
        self.cupos_disponibles -= personas
        self.secuencia += 1

    def liberar(self, personas: int) -> None:
        if personas < 1 or personas > self.cupos_reservados:
            raise ValueError("No se pueden liberar más cupos de los reservados.")
        self.cupos_disponibles += personas
        self.secuencia += 1

    def ajustar(
        self, cupos_totales: int, tarifa_dia: Decimal | None, aforo: int | None = None
    ) -> None:
        """Edita el día sin tocar lo ya reservado."""
        _validar_totales(cupos_totales, tarifa_dia, aforo, permitir_cero=True)
        if cupos_totales < self.cupos_reservados:
            raise CuposComprometidos(
                f"Ya hay {self.cupos_reservados} cupos reservados; "
                "rechace o cancele reservas antes de reducir."
            )
        reservados = self.cupos_reservados
        self.cupos_totales = cupos_totales
        self.cupos_disponibles = cupos_totales - reservados
        self.tarifa_dia = tarifa_dia
        self.version += 1
        self.secuencia += 1

    def evento(self) -> EventoDominio:
        """disponibilidad.actualizada: el estado completo del día, no la diferencia.

        Un día cerrado sale con cupos_totales = 0. Catalog lo usa solo para buscar;
        el cupo lo sigue garantizando booking con el bloqueo al reservar.
        """
        return EventoDominio(
            "disponibilidad.actualizada",
            {
                "servicio_id": str(self.servicio_id),
                "fecha": self.fecha.isoformat(),
                "cupos_totales": self.cupos_totales,
                "cupos_disponibles": self.cupos_disponibles,
                "version": self.secuencia,
            },
        )


def _validar_totales(
    cupos_totales: int,
    tarifa_dia: Decimal | None,
    aforo: int | None,
    permitir_cero: bool = False,
) -> None:
    minimo = 0 if permitir_cero else 1
    if cupos_totales < minimo:
        raise Validacion(f"Los cupos totales deben ser al menos {minimo}.")
    if tarifa_dia is not None and tarifa_dia < 0:
        raise Validacion("La tarifa del día no puede ser negativa.")
    if aforo is not None and cupos_totales > aforo:
        raise SuperaAforo(f"Los cupos superan la capacidad de carga oficial ({aforo}).")
