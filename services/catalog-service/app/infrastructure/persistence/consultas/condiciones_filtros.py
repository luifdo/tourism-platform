"""Condiciones SQL de FiltrosServicio, compartidas por la búsqueda y el mapa.

Los filtros de atributos son una sola contención `atributos @> filtro` sobre el índice GIN
`jsonb_path_ops` (migración 0004). La tabla de servicios debe llamarse `s` en la consulta.

Con `fecha`, se excluye el servicio cuyo día en `disponibilidad_proyeccion` no alcanza
para `personas` (un día cerrado tiene 0 cupos); el que no tiene dato se deja pasar
("sin confirmar"). La llave primaria (servicio, fecha) resuelve cada búsqueda.
"""

import json
from typing import Any

from app.application.dto.filtros_servicio import FiltrosServicio


def agregar_filtros(
    filtros: FiltrosServicio, condiciones: list[str], parametros: dict[str, Any]
) -> None:
    if filtros.tipos:
        condiciones.append("s.tipo = ANY(:tipos)")
        parametros["tipos"] = [t.value for t in filtros.tipos]
    if filtros.unidad_tarifa:
        condiciones.append("s.unidad_tarifa = :unidad_tarifa")
        parametros["unidad_tarifa"] = filtros.unidad_tarifa.value
    if filtros.fecha is not None:
        condiciones.append(
            "NOT EXISTS (SELECT 1 FROM disponibilidad_proyeccion d"
            " WHERE d.servicio_id = s.id AND d.fecha = :fecha"
            " AND d.cupos_disponibles < :personas)"
        )
        parametros["fecha"] = filtros.fecha
        parametros["personas"] = filtros.personas
    if (filtro := filtros.filtro_atributos()) is not None:
        condiciones.append("s.atributos @> CAST(:atributos AS jsonb)")
        parametros["atributos"] = json.dumps(filtro)


# Cupos del día según booking, para los resultados de la búsqueda (nulo: sin confirmar).
COLUMNA_CUPOS = (
    "(SELECT d.cupos_disponibles FROM disponibilidad_proyeccion d"
    " WHERE d.servicio_id = s.id AND d.fecha = :fecha) AS cupos"
)
