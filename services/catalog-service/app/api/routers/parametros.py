"""Conversión de parámetros de consulta compartida por los routers de lectura."""

import re
from datetime import date
from typing import Annotated

from fastapi import Query
from pydantic import BeforeValidator

from app.application.dto.filtros_servicio import FiltrosServicio
from app.domain.errors import DatoInvalido
from app.domain.value_objects.atributos.valores import NivelFisico, OpcionDietaria
from app.domain.value_objects.catalogos import Categoria, UnidadTarifa
from app.domain.value_objects.geo import Bbox, Coordenada
from app.domain.value_objects.tipo_servicio import TipoServicio

_FECHA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _fecha_iso(valor: object) -> object:
    """Pydantic acepta un número como fecha (timestamp: `fecha=0` sería el 1970-01-01); el
    contrato pide `AAAA-MM-DD` (`format: date`)."""
    if isinstance(valor, str) and not _FECHA_ISO.match(valor):
        raise ValueError("fecha en formato AAAA-MM-DD")
    return valor


Fecha = Annotated[date, BeforeValidator(_fecha_iso)]

# Tope de página: sin él, `pagina` enorme desborda el OFFSET de PostgreSQL (500, lo encontró
# Schemathesis). 10 000 páginas de 100 alcanzan para cualquier listado real.
PAGINA_MAXIMA = 10_000
Pagina = Annotated[int, Query(ge=1, le=PAGINA_MAXIMA)]


def bbox(valor: str) -> Bbox:
    """Vista del mapa como `minLon,minLat,maxLon,maxLat` (el formato de Leaflet `toBBoxString`)."""
    partes = valor.split(",")
    if len(partes) != 4:
        raise DatoInvalido(campo="bbox", regla="cuatro_valores")
    try:
        numeros = [float(p) for p in partes]
    except ValueError as exc:
        raise DatoInvalido(campo="bbox", regla="numero") from exc
    return Bbox.desde_lista(numeros)


def bbox_opcional(valor: str | None) -> Bbox | None:
    return bbox(valor) if valor is not None else None


def coordenada_opcional(lat: float | None, lon: float | None) -> Coordenada | None:
    """`lat` y `lon` van juntos o no van."""
    if lat is None and lon is None:
        return None
    if lat is None or lon is None:
        faltante = "lat" if lat is None else "lon"
        raise DatoInvalido(campo=faltante, regla="obligatorio")
    return Coordenada(lat=lat, lon=lon)


def categorias(valor: str | None) -> tuple[Categoria, ...]:
    """Lista separada por comas (`PLAYA,CULTURA`), como define el contrato."""
    if not valor:
        return ()
    try:
        return tuple(Categoria(c.strip().upper()) for c in valor.split(",") if c.strip())
    except ValueError as exc:
        raise DatoInvalido(campo="categoria", regla="formato") from exc


def tipos(valor: str | None) -> tuple[TipoServicio, ...]:
    """Lista separada por comas (`HOSTAL,HOTEL`), igual que `categoria`."""
    if not valor:
        return ()
    try:
        return tuple(TipoServicio(t.strip().upper()) for t in valor.split(",") if t.strip())
    except ValueError as exc:
        raise DatoInvalido(campo="tipo", regla="formato") from exc


def filtros_servicio(
    tipo: Annotated[str | None, Query(description="Uno o varios, separados por comas")] = None,
    unidad_tarifa: UnidadTarifa | None = None,
    idioma_atencion: Annotated[str | None, Query(pattern=r"^[a-z]{2}$")] = None,
    accesible: bool | None = None,
    mascotas: bool | None = None,
    apto_ninos: bool | None = None,
    opcion_dietaria: OpcionDietaria | None = None,
    nivel_fisico: NivelFisico | None = None,
    acepta_pago_digital: bool | None = None,
    ofrece_credito: bool | None = None,
    fecha: Annotated[Fecha | None, Query(description="Día con cupo según booking")] = None,
    personas: Annotated[int, Query(ge=1, description="Personas que necesitan cupo")] = 1,
) -> FiltrosServicio:
    """Parámetros de tipo y atributos que comparten `/buscar` y `/mapa/servicios`."""
    return FiltrosServicio(
        tipos=tipos(tipo),
        unidad_tarifa=unidad_tarifa,
        idioma_atencion=idioma_atencion,
        accesible=accesible,
        mascotas=mascotas,
        apto_ninos=apto_ninos,
        opcion_dietaria=opcion_dietaria,
        nivel_fisico=nivel_fisico,
        acepta_pago_digital=acepta_pago_digital,
        ofrece_credito=ofrece_credito,
        fecha=fecha,
        personas=personas,
    )
