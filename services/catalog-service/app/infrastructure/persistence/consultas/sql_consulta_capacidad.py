"""Cargas para la capacidad de carga (implementa ConsultaCapacidad).

Se calcula al consultar, no con un CronJob: la suma por día usa el índice
`ix_reserva_fecha_servicio` de `reserva_proyeccion` y se consulta poco (Entidad y chatbot).
Un servicio cuenta en la zona en la que está hoy.
"""

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.carga_de_servicio import CargaDeServicio
from app.application.dto.cargas_capacidad import CargasCapacidad
from app.application.dto.cargas_de_zona import CargasDeZona
from app.application.dto.zona_resumen import ZonaResumen
from app.domain.ports.reloj import Reloj
from app.domain.services.calculadora_saturacion import CargaServicio
from app.domain.value_objects.texto_traducido import TextoTraducido

_CARGAS = """
    SELECT z.id AS zona_id, z.codigo, z.nombre AS zona_nombre,
           s.id AS servicio_id, s.nombre AS servicio_nombre, s.activo,
           s.capacidad_aforo_diario, coalesce(r.personas, 0) AS personas
    FROM zona z
    LEFT JOIN atractivo_servicio s ON s.zona_id = z.id
    LEFT JOIN (
        SELECT servicio_id, sum(numero_personas)::int AS personas
        FROM reserva_proyeccion
        WHERE fecha_reserva = :fecha AND estado IN ('SOLICITADA', 'CONFIRMADA')
        GROUP BY servicio_id
    ) r ON r.servicio_id = s.id
    WHERE z.activa {filtro}
    ORDER BY z.codigo, s.id
"""


class SqlConsultaCapacidad:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession], reloj: Reloj) -> None:
        self._sesiones = sesiones
        self._reloj = reloj

    async def cargas(self, fecha: date, zona: str | None = None) -> CargasCapacidad:
        parametros: dict[str, Any] = {"fecha": fecha}
        filtro = ""
        if zona is not None:
            filtro, parametros["zona"] = "AND z.codigo = :zona", zona
        async with self._sesiones() as session:
            filas = (await session.execute(text(_CARGAS.format(filtro=filtro)), parametros)).all()

        zonas: dict[Any, tuple[ZonaResumen, list[CargaDeServicio]]] = {}
        for f in filas:
            _, servicios = zonas.setdefault(
                f.zona_id, (ZonaResumen(f.codigo, TextoTraducido(**f.zona_nombre)), [])
            )
            if f.servicio_id is not None:
                servicios.append(
                    CargaDeServicio(
                        servicio_id=f.servicio_id,
                        nombre=TextoTraducido(**f.servicio_nombre),
                        carga=CargaServicio(f.personas, f.capacidad_aforo_diario, f.activo),
                    )
                )
        return CargasCapacidad(
            fecha=fecha,
            zonas=tuple(
                CargasDeZona(zona_id=zona_id, zona=resumen, servicios=tuple(servicios))
                for zona_id, (resumen, servicios) in zonas.items()
            ),
            leido_en=self._reloj.ahora(),
        )
