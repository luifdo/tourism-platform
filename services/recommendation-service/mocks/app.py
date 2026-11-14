"""mock-plataforma: responde como catalog, booking y review con datos fijos (Fase 2).

Solo implementa las rutas que usan las tools del Módulo 5, con las formas de
contracts/openapi/{catalog,booking,review}.yaml. No forma parte del servicio.
"""

import unicodedata
from datetime import date, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from mocks.datos import (
    ALERTAS,
    ETIQUETAS,
    RESENAS,
    RESERVAS_TURISTA,
    SERVICIOS,
    SERVICIOS_POR_ID,
    TURISTA_CON_HISTORIAL,
    ZONAS,
)

app = FastAPI(title="mock-plataforma")

ZonaQuery = Annotated[str | None, Query(pattern=r"^[a-z0-9-]{2,40}$")]
FECHA_CALCULO = "2026-10-29T08:00:00-05:00"
REGLA_CANCELACION = {
    "es": "Regla de la plataforma: puedes cancelar una reserva solicitada en cualquier momento "
    "y una confirmada hasta las 23:59 del día anterior a la fecha reservada.",
    "en": "Platform rule: you can cancel a requested booking at any time and a confirmed one "
    "until 23:59 the day before the booked date.",
}


class MockError(Exception):
    def __init__(self, estado: int, codigo: str, mensaje: str) -> None:
        self.estado, self.codigo, self.mensaje = estado, codigo, mensaje


@app.exception_handler(MockError)
async def _error_mock(_: Request, exc: MockError) -> JSONResponse:
    return _error(exc.estado, exc.codigo, exc.mensaje)


@app.exception_handler(RequestValidationError)
async def _validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Los contratos responden 400 VALIDACION, no el 422 de FastAPI.
    return _error(400, "VALIDACION", str(exc.errors()[0]["msg"]))


def _error(estado: int, codigo: str, mensaje: str) -> JSONResponse:
    cuerpo = {"error": codigo, "message": mensaje, "correlation_id": str(uuid4())}
    return JSONResponse(cuerpo, status_code=estado)


def _idioma(accept_language: str | None) -> str:
    return "en" if accept_language and accept_language.lower().startswith("en") else "es"


def _json(cuerpo: object, idioma: str | None = None) -> JSONResponse:
    cabeceras = {"Content-Language": idioma} if idioma else None
    return JSONResponse(cuerpo, headers=cabeceras)


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )


def _zona_resumen(codigo: str | None) -> dict | None:
    return {"codigo": codigo, "nombre": ZONAS[codigo]["nombre"]} if codigo else None


def _puntuaciones(servicio_id: UUID) -> list[int]:
    return [r[0] for r in RESENAS.get(servicio_id, [])]


def _cupos(servicio: dict, dia: date) -> int:
    # Determinista: cambia con el día y deja algunos días sin cupo.
    return max(0, servicio["aforo"] - (dia.toordinal() * 7 + servicio["aforo"]) % 15)


def _resumen_servicio(servicio: dict, idioma: str) -> dict:
    puntuaciones = _puntuaciones(servicio["id"])
    return {
        "id": str(servicio["id"]),
        "nombre": servicio["nombre"],
        "tipo": servicio["tipo"],
        "categoria": servicio["categoria"],
        "zona": _zona_resumen(servicio["zona"]),
        "ubicacion": servicio["ubicacion"],
        "tarifa_base": servicio["tarifa_base"],
        "unidad_tarifa": servicio["unidad_tarifa"],
        "unidad_tarifa_etiqueta": ETIQUETAS[idioma][servicio["unidad_tarifa"]],
        "calificacion_promedio": (
            round(sum(puntuaciones) / len(puntuaciones), 2) if puntuaciones else None
        ),
        "total_resenas": len(puntuaciones),
        "imagen_principal": None,
    }


def _alerta(alerta: dict, idioma: str) -> dict:
    return {
        "id": str(alerta["id"]),
        "nivel": alerta["nivel"],
        "nivel_etiqueta": ETIQUETAS[idioma][alerta["nivel"]],
        "mensaje": alerta["mensaje"],
        "servicio_id": str(alerta["servicio_id"]) if alerta["servicio_id"] else None,
        "zona": _zona_resumen(alerta["zona"]),
        "fecha_expiracion": alerta["fecha_expiracion"],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------- catalog ----------


@app.get("/api/catalog/buscar")
def buscar(
    accept_language: Annotated[str | None, Header()] = None,
    texto: Annotated[str | None, Query(max_length=200)] = None,
    categoria: str | None = None,
    zona: ZonaQuery = None,
    precio_min: Annotated[float | None, Query(ge=0)] = None,
    precio_max: Annotated[float | None, Query(ge=0)] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    fecha: date | None = None,
    personas: Annotated[int, Query(ge=1)] = 1,
    pagina: Annotated[int, Query(ge=1, le=10000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=50)] = 20,
) -> JSONResponse:
    idioma = _idioma(accept_language)
    if (lat is None) != (lon is None):
        raise MockError(400, "VALIDACION", "lat y lon van juntos.")
    if personas != 1 and fecha is None:
        raise MockError(400, "VALIDACION", "personas distinto de 1 requiere fecha.")
    categorias = set(categoria.split(",")) if categoria else None
    palabras = _sin_tildes(texto).split() if texto else []

    def cumple(s: dict) -> bool:
        contenido = _sin_tildes(f"{s['nombre']} {s['descripcion']}")
        return (
            all(p in contenido for p in palabras)
            and (categorias is None or s["categoria"] in categorias)
            and (zona is None or s["zona"] == zona)
            and (precio_min is None or s["tarifa_base"] >= precio_min)
            and (precio_max is None or s["tarifa_base"] <= precio_max)
            and (fecha is None or _cupos(s, fecha) >= personas)
        )

    encontrados = [
        _resumen_servicio(s, idioma) | _con_cupos(s, fecha) for s in SERVICIOS if cumple(s)
    ]
    encontrados.sort(key=lambda s: s["calificacion_promedio"] or 0, reverse=True)
    inicio = (pagina - 1) * tamano
    cuerpo = {
        "items": encontrados[inicio : inicio + tamano],
        "pagina": pagina,
        "tamano": tamano,
        "total": len(encontrados),
    }
    return _json(cuerpo, idioma)


def _con_cupos(servicio: dict, fecha: date | None) -> dict:
    if fecha is None:
        return {"distancia_m": None, "cupos_disponibles": None, "disponibilidad_confirmada": None}
    return {
        "distancia_m": None,
        "cupos_disponibles": _cupos(servicio, fecha),
        "disponibilidad_confirmada": True,
    }


@app.get("/api/catalog/servicios/{servicio_id}")
def detalle(
    servicio_id: UUID, accept_language: Annotated[str | None, Header()] = None
) -> JSONResponse:
    idioma = _idioma(accept_language)
    servicio = SERVICIOS_POR_ID.get(servicio_id)
    if servicio is None:
        raise MockError(404, "NO_ENCONTRADO", "El servicio no existe o está inactivo.")
    alertas = [
        _alerta(a, idioma)
        for a in ALERTAS
        if a["zona"] == servicio["zona"] or a["servicio_id"] == servicio_id
    ]
    aviso = servicio["aviso_pagos"]
    cuerpo = _resumen_servicio(servicio, idioma) | {
        "descripcion": servicio["descripcion"],
        "capacidad_aforo_diario": servicio["aforo"],
        "imagenes_urls": [],
        "prestador": {
            "id": str(UUID(int=servicio_id.int ^ 1)),
            "razon_social": servicio["prestador"],
            "telefono": "+57 300 000 0000",
            "politica_cancelacion": None,
        },
        "regla_base_cancelacion": REGLA_CANCELACION[idioma],
        "alertas": alertas,
        "atributos": {},
        "etiquetas": {},
        "aviso_pagos": (
            {"importante": True, "recomendacion_dinero": "EFECTIVO", "mensaje": aviso}
            if aviso
            else None
        ),
    }
    return _json(cuerpo, idioma)


@app.get("/api/catalog/alertas")
def alertas(
    accept_language: Annotated[str | None, Header()] = None,
    zona: ZonaQuery = None,
    servicio_id: UUID | None = None,
) -> JSONResponse:
    idioma = _idioma(accept_language)
    servicio = SERVICIOS_POR_ID.get(servicio_id) if servicio_id else None
    vigentes = [
        a
        for a in ALERTAS
        if (zona is None or a["zona"] == zona)
        and (
            servicio_id is None
            or a["servicio_id"] == servicio_id
            or (servicio is not None and a["zona"] == servicio["zona"])
        )
    ]
    orden = {"CRITICA": 0, "PREVENTIVA": 1, "INFORMATIVA": 2}
    vigentes.sort(key=lambda a: orden[a["nivel"]])
    return _json([_alerta(a, idioma) for a in vigentes], idioma)


@app.get("/api/catalog/analitica/capacidad")
def capacidad(
    accept_language: Annotated[str | None, Header()] = None,
    x_usuario_id: Annotated[str | None, Header()] = None,
    x_usuario_rol: Annotated[str | None, Header()] = None,
    zona: ZonaQuery = None,
    fecha: date | None = None,
) -> JSONResponse:
    idioma = _idioma(accept_language)
    if not x_usuario_id or not x_usuario_rol:
        raise MockError(401, "NO_AUTENTICADO", "Falta la identidad del usuario.")
    if x_usuario_rol not in {"Turista", "Entidad", "Admin"}:
        raise MockError(403, "PROHIBIDO", "El rol no puede consultar la capacidad.")
    if zona is not None and zona not in ZONAS:
        raise MockError(404, "NO_ENCONTRADO", "La zona no existe.")
    dia = (fecha or date(2026, 10, 29)).isoformat()
    codigos = [zona] if zona else list(ZONAS)
    codigos.sort(key=lambda c: ZONAS[c]["indice"], reverse=True)
    cuerpo = []
    for codigo in codigos:
        datos = ZONAS[codigo]
        fila = {
            "zona": _zona_resumen(codigo),
            "fecha": dia,
            "nivel": datos["nivel"],
            "nivel_etiqueta": ETIQUETAS[idioma][datos["nivel"]],
        }
        if x_usuario_rol != "Turista":
            fila |= {"indice": datos["indice"], "calculado_en": FECHA_CALCULO}
        cuerpo.append(fila)
    return _json(cuerpo, idioma)


# ---------- booking ----------


@app.get("/api/bookings/disponibilidad")
def disponibilidad(servicio_id: UUID, desde: date, hasta: date) -> JSONResponse:
    if hasta < desde or (hasta - desde).days > 62:
        raise MockError(400, "VALIDACION", "El rango debe ir de desde a hasta, máximo 62 días.")
    servicio = SERVICIOS_POR_ID.get(servicio_id)
    dias = []
    if servicio is not None:
        for n in range((hasta - desde).days + 1):
            dia = desde + timedelta(days=n)
            dias.append(
                {
                    "fecha": dia.isoformat(),
                    "cupos_disponibles": _cupos(servicio, dia),
                    "tarifa_dia": None,
                }
            )
    return _json({"servicio_id": str(servicio_id), "dias": dias})


@app.get("/api/bookings/mis-reservas")
def mis_reservas(
    x_usuario_id: Annotated[UUID | None, Header()] = None,
    x_usuario_rol: Annotated[str | None, Header()] = None,
    estado: str | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JSONResponse:
    if x_usuario_id is None:
        raise MockError(401, "NO_AUTENTICADO", "Falta la identidad del usuario.")
    if x_usuario_rol != "Turista":
        raise MockError(403, "PROHIBIDO", "Solo un turista consulta su historial.")
    propias = RESERVAS_TURISTA if x_usuario_id == TURISTA_CON_HISTORIAL else []
    items = [
        {
            "id": str(UUID(int=i + 1)),
            "servicio_id": str(servicio_id),
            "turista_id": str(x_usuario_id),
            "prestador_id": str(UUID(int=servicio_id.int ^ 1)),
            "fecha_reserva": fecha,
            "numero_personas": personas,
            "estado": est,
            "expira_en": None,
            "motivo": None,
            "cancelada_por": None,
            "version": 1,
            "creado_en": f"{fecha}T09:00:00-05:00",
        }
        for i, (servicio_id, fecha, personas, est) in enumerate(propias)
        if estado is None or est == estado
    ]
    items.sort(key=lambda r: r["fecha_reserva"], reverse=True)
    inicio = (pagina - 1) * tamano
    return _json(
        {
            "items": items[inicio : inicio + tamano],
            "pagina": pagina,
            "tamano": tamano,
            "total": len(items),
        }
    )


# ---------- review ----------


@app.get("/api/reviews/servicios/{servicio_id}/resenas")
def resenas(
    servicio_id: UUID,
    accept_language: Annotated[str | None, Header()] = None,
    orden: str = "recientes",
    pagina: Annotated[int, Query(ge=1, le=10000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=50)] = 20,
) -> JSONResponse:
    idioma = _idioma(accept_language)
    autor = "Turista verificado" if idioma == "es" else "Verified tourist"
    items = [
        {
            "id": str(UUID(int=(servicio_id.int + n) % 2**128)),
            "servicio_id": str(servicio_id),
            "autor": autor,
            "mes_visita": mes,
            "puntuacion": puntuacion,
            "aspectos": {},
            "aspectos_etiquetas": {},
            "comentario": comentario,
            "respuesta": None,
            "creada_en": f"{mes}-{dia:02d}T12:00:00-05:00",
            "editada_en": None,
        }
        for n, (puntuacion, comentario, mes, dia) in enumerate(RESENAS.get(servicio_id, []))
    ]
    if orden == "mejores":
        items.sort(key=lambda r: r["puntuacion"], reverse=True)
    elif orden == "peores":
        items.sort(key=lambda r: r["puntuacion"])
    else:
        items.sort(key=lambda r: r["creada_en"], reverse=True)
    inicio = (pagina - 1) * tamano
    cuerpo = {
        "items": items[inicio : inicio + tamano],
        "pagina": pagina,
        "tamano": tamano,
        "total": len(items),
    }
    return _json(cuerpo, idioma)


@app.get("/api/reviews/servicios/{servicio_id}/resumen")
def resumen(servicio_id: UUID) -> JSONResponse:
    puntuaciones = _puntuaciones(servicio_id)
    return _json(
        {
            "servicio_id": str(servicio_id),
            "total": len(puntuaciones),
            "promedio": round(sum(puntuaciones) / len(puntuaciones), 2) if puntuaciones else None,
            "distribucion": {str(n): puntuaciones.count(n) for n in range(1, 6)},
            "aspectos": {},
        }
    )
