"""CSV del reporte de demanda (UC38) para el personal de la Entidad, en español.

Formato pensado para Excel en español: separador `;`, coma decimal y UTF-8 con BOM (sin el
BOM, Excel muestra mal las tildes). Se genera fila por fila, en streaming.

Inyección de fórmulas: el nombre de un servicio lo escribe el prestador; si empieza por
`=`, `+`, `-`, `@` (o tabulador / retorno), Excel lo ejecutaría como fórmula al abrir el
archivo. Esas celdas se escriben con un apóstrofo delante para que queden como texto.
"""

import csv
import io
from collections.abc import AsyncIterator, Iterable

from app.api.i18n.etiquetas import etiqueta
from app.application.dto.fila_reporte_demanda import FilaReporteDemanda
from app.domain.value_objects.idioma import Idioma

BOM = "﻿"
SEPARADOR = ";"
ENCABEZADOS = (
    "Fecha",
    "Zona",
    "Servicio",
    "Categoría",
    "Tipo",
    "Personas solicitadas",
    "Personas confirmadas",
    "Personas finalizadas",
    "Personas canceladas",
    "Total de personas",
    "Capacidad recomendada (personas)",
    "Índice de saturación",
    "Intenciones de visita",
)
_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")


def texto_seguro(valor: str) -> str:
    return f"'{valor}" if valor.startswith(_PELIGROSOS) else valor


def decimal(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


def nombre_archivo(desde: str, hasta: str) -> str:
    return f"demanda_{desde}_{hasta}.csv"


def _linea(celdas: Iterable[object]) -> str:
    salida = io.StringIO()
    csv.writer(salida, delimiter=SEPARADOR, lineterminator="\r\n").writerow(celdas)
    return salida.getvalue()


def _celdas(fila: FilaReporteDemanda) -> list[object]:
    return [
        fila.fecha.isoformat(),
        texto_seguro(fila.zona or ""),
        texto_seguro(fila.servicio),
        etiqueta(fila.categoria, Idioma.ES),
        etiqueta(fila.tipo, Idioma.ES),
        fila.personas_solicitadas,
        fila.personas_confirmadas,
        fila.personas_finalizadas,
        fila.personas_canceladas,
        fila.total_personas,
        fila.capacidad_recomendada,
        decimal(fila.indice),
        fila.intenciones_visita,
    ]


async def generar_csv(filas: AsyncIterator[FilaReporteDemanda]) -> AsyncIterator[bytes]:
    yield (BOM + _linea(ENCABEZADOS)).encode("utf-8")
    async for fila in filas:
        yield _linea(_celdas(fila)).encode("utf-8")
