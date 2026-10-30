"""Convierte a texto normal el Markdown que a veces escribe el modelo.

La PWA muestra la respuesta como texto: una tabla o unas negritas en Markdown se verían como
símbolos sueltos (`| --- |`, `**`). Las instrucciones piden texto plano; esto es la red de
seguridad para cuando el modelo no obedece.
"""

import re

_SEPARADOR_DE_TABLA = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_FILA_DE_TABLA = re.compile(r"^\s*\|.*\|\s*$")
_TITULO = re.compile(r"^\s{0,3}#{1,6}\s+")
_VINETA = re.compile(r"^(\s*)[-*+]\s+")
_ENFASIS = re.compile(r"(\*\*|__)(.+?)\1|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
_CODIGO = re.compile(r"`([^`]*)`")
_ENLACE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def a_texto_plano(texto: str) -> str:
    lineas = texto.splitlines()
    salida: list[str] = []
    encabezado: list[str] | None = None
    for indice, linea in enumerate(lineas):
        if _SEPARADOR_DE_TABLA.match(linea):
            continue
        if _FILA_DE_TABLA.match(linea):
            celdas = [_en_linea(c.strip()) for c in linea.strip().strip("|").split("|")]
            siguiente = lineas[indice + 1] if indice + 1 < len(lineas) else ""
            if encabezado is None and _SEPARADOR_DE_TABLA.match(siguiente):
                encabezado = celdas
                continue
            salida.append(_fila(celdas, encabezado))
            continue
        encabezado = None
        linea = _TITULO.sub("", linea)
        linea = _VINETA.sub(r"\1• ", linea)
        salida.append(_en_linea(linea))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip()


def _en_linea(texto: str) -> str:
    texto = _ENLACE.sub(r"\1", texto)
    texto = _CODIGO.sub(r"\1", texto)
    return _ENFASIS.sub(lambda m: m.group(2) or m.group(3), texto)


def _fila(celdas: list[str], encabezado: list[str] | None) -> str:
    """Una fila de tabla como frase: «Servicio: Buceo · Fecha: 8 nov · …»."""
    if encabezado and len(encabezado) == len(celdas):
        partes = [f"{titulo}: {valor}" for titulo, valor in zip(encabezado, celdas, strict=True)]
    else:
        partes = celdas
    return "• " + " · ".join(p for p in partes if p)
