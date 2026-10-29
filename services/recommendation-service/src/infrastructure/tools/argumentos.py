"""Argumentos de cada tool: validan lo que pide el modelo y generan su JSON Schema.

Un mismo modelo de Pydantic sirve para las dos cosas, así la declaración que ve el
modelo y la validación nunca se separan. Los argumentos que el modelo agregue de más
(por ejemplo un `turista_id`) se descartan.
"""

import re
import unicodedata
from datetime import date, timedelta
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


def _normalizar_zona(valor: Any) -> Any:
    """`"Centro Histórico"` → `centro-historico`: el modelo a veces escribe el nombre."""
    if not isinstance(valor, str):
        return valor
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", valor) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[\s_]+", "-", sin_tildes.strip().lower())


Zona = Annotated[
    str,
    BeforeValidator(_normalizar_zona),
    StringConstraints(pattern=r"^[a-z0-9-]{2,40}$"),
]
Categoria = Literal[
    "PLAYA", "NATURALEZA", "CULTURA", "GASTRONOMIA", "AVENTURA", "ALOJAMIENTO", "TRANSPORTE"
]
MAX_DIAS_DISPONIBILIDAD = 62

_DESCRIPCION_ZONA = (
    "Código de la zona, tal como aparece en `zona_codigo` de otras tools (por ejemplo "
    "`minca` o `tayrona`). Si no lo conoces, llama a `presion_capacidad_carga` sin zona."
)


class _Argumentos(BaseModel):
    model_config = ConfigDict(extra="ignore")


class BuscarServicios(_Argumentos):
    texto: str | None = Field(
        None, max_length=200, description="Palabras clave sobre nombre y descripción."
    )
    categorias: list[Categoria] | None = Field(None, description="Una o varias categorías.")
    zona: Zona | None = Field(None, description=_DESCRIPCION_ZONA)
    precio_max: float | None = Field(None, ge=0, description="Tarifa máxima en COP.")
    fecha: date | None = Field(
        None, description="Día de la visita (AAAA-MM-DD); deja solo servicios con cupo ese día."
    )
    personas: int | None = Field(
        None, ge=1, le=50, description="Personas que necesitan cupo; requiere `fecha`."
    )
    lat: float | None = Field(
        None, ge=-90, le=90, description="Latitud del punto cerca del cual buscar; va con `lon`."
    )
    lon: float | None = Field(
        None, ge=-180, le=180, description="Longitud del punto cerca del cual buscar; va con `lat`."
    )

    @model_validator(mode="after")
    def _coherentes(self) -> Self:
        if (self.lat is None) != (self.lon is None):
            raise ValueError("`lat` y `lon` van juntos")
        if self.personas not in (None, 1) and self.fecha is None:
            raise ValueError("`personas` requiere `fecha`")
        return self


class DetalleServicio(_Argumentos):
    servicio_id: UUID = Field(description="Identificador del servicio, tal como lo dio otra tool.")


class ConsultarDisponibilidad(_Argumentos):
    servicio_id: UUID = Field(description="Identificador del servicio.")
    desde: date = Field(description="Primer día a consultar (AAAA-MM-DD).")
    hasta: date | None = Field(
        None, description="Último día a consultar; por defecto el mismo `desde`. Máximo 62 días."
    )

    @model_validator(mode="after")
    def _rango(self) -> Self:
        hasta = self.hasta or self.desde
        if hasta < self.desde:
            raise ValueError("`hasta` no puede ser anterior a `desde`")
        if hasta - self.desde > timedelta(days=MAX_DIAS_DISPONIBILIDAD):
            raise ValueError(f"el rango no puede pasar de {MAX_DIAS_DISPONIBILIDAD} días")
        return self


class HistorialTurista(_Argumentos):
    """Sin parámetros: el turista lo pone el servidor, nunca el modelo."""


class ResenasServicio(_Argumentos):
    servicio_id: UUID = Field(description="Identificador del servicio.")


class PresionCapacidadCarga(_Argumentos):
    zona: Zona | None = Field(None, description=f"{_DESCRIPCION_ZONA} Sin zona, devuelve todas.")
    fecha: date | None = Field(None, description="Día a consultar (AAAA-MM-DD); por defecto hoy.")


class AlertasOficiales(_Argumentos):
    zona: Zona | None = Field(None, description=_DESCRIPCION_ZONA)
    servicio_id: UUID | None = Field(
        None, description="Solo las alertas de este servicio y de su zona."
    )


def esquema(modelo: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema plano: sin títulos, sin `default: null` y sin `anyOf` con null.

    Tampoco lleva `pattern`: algunos proveedores (Groq) validan los argumentos con el esquema
    y, si no cumplen, cortan toda la petición (`tool_use_failed`). La validación la hace
    `ejecutar`, que le devuelve al modelo un error que puede corregir.
    """
    return _simplificar(modelo.model_json_schema())


_FUERA_DEL_ESQUEMA = {"title", "pattern"}


def _simplificar(nodo: Any) -> Any:
    if isinstance(nodo, list):
        return [_simplificar(n) for n in nodo]
    if not isinstance(nodo, dict):
        return nodo
    nodo = {
        k: v
        for k, v in nodo.items()
        if k not in _FUERA_DEL_ESQUEMA and not (k == "default" and v is None)
    }
    opciones = nodo.get("anyOf")
    if opciones is not None:
        sin_nulo = [o for o in opciones if o != {"type": "null"}]
        if len(sin_nulo) == 1:
            nodo = {k: v for k, v in nodo.items() if k != "anyOf"} | sin_nulo[0]
    return {k: _simplificar(v) for k, v in nodo.items()}
