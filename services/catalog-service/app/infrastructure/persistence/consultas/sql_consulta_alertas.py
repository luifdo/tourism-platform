"""Lectura de alertas: vigentes (público) y panel de la Entidad (implementa ConsultaAlertas)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.alerta_editable import AlertaEditable
from app.application.dto.alerta_vista import AlertaVista
from app.application.dto.estado_alerta import EstadoAlerta
from app.application.dto.pagina_alertas_entidad import PaginaAlertasEntidad
from app.application.dto.zona_resumen import ZonaResumen
from app.domain.value_objects.catalogos import NivelAlerta
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.infrastructure.persistence.modelos.alerta_oficial import AlertaOficialModelo
from app.infrastructure.persistence.modelos.zona import ZonaModelo
from app.infrastructure.persistence.repositorios.alerta_repository import alerta_desde_modelo

_BASE = """
    SELECT a.id, a.nivel, a.mensaje, a.servicio_id, a.fecha_expiracion,
           z.codigo AS zona_codigo, z.nombre AS zona_nombre
    FROM alerta_oficial a
    LEFT JOIN zona z ON z.id = a.zona_id
    WHERE a.activa AND a.fecha_expiracion > :ahora
"""
# Una alerta de zona afecta a todos sus servicios, y una de servicio afecta a su zona.
_FILTRO_ZONA = """
    AND (z.codigo = :zona
         OR a.servicio_id IN (SELECT s.id FROM atractivo_servicio s
                              JOIN zona zs ON zs.id = s.zona_id WHERE zs.codigo = :zona))
"""
_FILTRO_SERVICIO = """
    AND (a.servicio_id = :servicio_id
         OR a.zona_id = (SELECT s.zona_id FROM atractivo_servicio s WHERE s.id = :servicio_id))
"""
ORDEN_POR_NIVEL = """
    ORDER BY CASE a.nivel WHEN 'CRITICA' THEN 0 WHEN 'PREVENTIVA' THEN 1 ELSE 2 END,
             a.fecha_expiracion
"""


def alerta_desde_fila(fila: Any) -> AlertaVista:
    zona = (
        ZonaResumen(codigo=fila.zona_codigo, nombre=TextoTraducido(**fila.zona_nombre))
        if fila.zona_codigo
        else None
    )
    return AlertaVista(
        id=fila.id,
        nivel=NivelAlerta(fila.nivel),
        mensaje=TextoTraducido(**fila.mensaje),
        servicio_id=fila.servicio_id,
        zona=zona,
        fecha_expiracion=fila.fecha_expiracion,
    )


class SqlConsultaAlertas:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones

    async def vigentes(
        self, ahora: datetime, zona: str | None = None, servicio_id: UUID | None = None
    ) -> list[AlertaVista]:
        sql = _BASE
        parametros: dict[str, Any] = {"ahora": ahora}
        if zona is not None:
            sql += _FILTRO_ZONA
            parametros["zona"] = zona
        if servicio_id is not None:
            sql += _FILTRO_SERVICIO
            parametros["servicio_id"] = servicio_id
        async with self._sesiones() as session:
            filas = (await session.execute(text(sql + ORDEN_POR_NIVEL), parametros)).all()
        return [alerta_desde_fila(f) for f in filas]

    async def de_entidad(
        self, ahora: datetime, estado: EstadoAlerta | None, pagina: int, tamano: int
    ) -> PaginaAlertasEntidad:
        a = AlertaOficialModelo
        condicion: ColumnElement[bool] | None = {
            EstadoAlerta.VIGENTE: a.activa & (a.fecha_expiracion > ahora),
            EstadoAlerta.VENCIDA: a.activa & (a.fecha_expiracion <= ahora),
            EstadoAlerta.RETIRADA: ~a.activa,
            None: None,
        }[estado]
        consulta = select(a, ZonaModelo.codigo).outerjoin(ZonaModelo, ZonaModelo.id == a.zona_id)
        conteo = select(func.count()).select_from(a)
        if condicion is not None:
            consulta, conteo = consulta.where(condicion), conteo.where(condicion)
        async with self._sesiones() as session:
            total = await session.scalar(conteo) or 0
            filas = (
                await session.execute(
                    consulta.order_by(a.creada_en.desc(), a.id)
                    .limit(tamano)
                    .offset((pagina - 1) * tamano)
                )
            ).all()
        items = tuple(AlertaEditable(alerta_desde_modelo(f[0]), f[1]) for f in filas)
        return PaginaAlertasEntidad(
            items=items, pagina=pagina, tamano=tamano, total=total, ahora=ahora
        )
