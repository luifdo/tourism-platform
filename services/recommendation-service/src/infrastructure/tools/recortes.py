"""Reducen cada respuesta de la plataforma a lo que el modelo necesita.

Lo que no está aquí no viaja al proveedor de IA: ni ids internos de reservas o
prestadores, ni teléfonos, ni autores de reseñas (Ley 1581). Si la respuesta no tiene la
forma del contrato, fallan con KeyError o TypeError y la tool responde RESPUESTA_INESPERADA.
"""

from typing import Any

MAX_DESCRIPCION = 600
MAX_COMENTARIO = 300


def _corto(texto: str | None, maximo: int) -> str | None:
    if texto is None or len(texto) <= maximo:
        return texto
    return texto[: maximo - 1].rstrip() + "…"


def _zona(zona: dict[str, Any] | None) -> str | None:
    return zona["nombre"] if zona else None


def _zona_codigo(zona: dict[str, Any] | None) -> str | None:
    # El modelo lo copia en el argumento `zona` de las demás tools.
    return zona["codigo"] if zona else None


def _servicio(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "nombre": item["nombre"],
        "categoria": item["categoria"],
        "tipo": item["tipo"],
        "zona": _zona(item.get("zona")),
        "zona_codigo": _zona_codigo(item.get("zona")),
        "tarifa_base": item["tarifa_base"],
        "unidad_tarifa": item.get("unidad_tarifa_etiqueta") or item["unidad_tarifa"],
        "calificacion_promedio": item.get("calificacion_promedio"),
        "total_resenas": item.get("total_resenas", 0),
    }


def busqueda(cuerpo: dict[str, Any], capacidad: Any = None, alertas: Any = None) -> dict[str, Any]:
    """`capacidad` y `alertas` son opcionales: si faltan o vienen mal, se omiten."""
    niveles = _niveles_por_zona(capacidad)
    vigentes = alertas if isinstance(alertas, list) else None
    servicios = []
    for item in cuerpo["items"]:
        servicio = _servicio(item)
        if item.get("cupos_disponibles") is not None:
            servicio["cupos_disponibles"] = item["cupos_disponibles"]
        if item.get("disponibilidad_confirmada") is False:
            servicio["disponibilidad_confirmada"] = False
        zona = servicio["zona_codigo"]
        if zona in niveles:
            servicio["nivel_capacidad_zona"] = niveles[zona]
        if vigentes is not None:
            servicio["alertas"] = [
                {"nivel": a["nivel"], "mensaje": a["mensaje"]}
                for a in vigentes
                if a.get("servicio_id") == item["id"]
                or (zona is not None and _zona_codigo(a.get("zona")) == zona)
            ]
        servicios.append(servicio)
    return {"total": cuerpo["total"], "servicios": servicios}


def _niveles_por_zona(capacidad: Any) -> dict[str, str]:
    if not isinstance(capacidad, list):
        return {}
    try:
        return {c["zona"]["codigo"]: c["nivel"] for c in capacidad}
    except (KeyError, TypeError):
        return {}


def detalle(cuerpo: dict[str, Any]) -> dict[str, Any]:
    aviso = cuerpo.get("aviso_pagos")
    return _servicio(cuerpo) | {
        "descripcion": _corto(cuerpo["descripcion"], MAX_DESCRIPCION),
        "prestador": cuerpo["prestador"]["razon_social"],
        "aviso_pagos": aviso["mensaje"] if aviso else None,
        "regla_cancelacion": cuerpo["regla_base_cancelacion"],
        "alertas": [{"nivel": a["nivel"], "mensaje": a["mensaje"]} for a in cuerpo["alertas"]],
    }


def disponibilidad(cuerpo: dict[str, Any]) -> dict[str, Any]:
    return {
        "servicio_id": cuerpo["servicio_id"],
        "dias": [
            {
                "fecha": d["fecha"],
                "cupos_disponibles": d["cupos_disponibles"],
                "tarifa_dia": d.get("tarifa_dia"),
            }
            for d in cuerpo["dias"]
        ],
    }


def historial(cuerpo: dict[str, Any]) -> dict[str, Any]:
    return {
        "reservas": [
            {
                "servicio_id": r["servicio_id"],
                "fecha": r["fecha_reserva"],
                "personas": r["numero_personas"],
                "estado": r["estado"],
            }
            for r in cuerpo["items"]
        ]
    }


def resenas(resumen: dict[str, Any], pagina: dict[str, Any]) -> dict[str, Any]:
    return {
        "servicio_id": resumen["servicio_id"],
        "promedio": resumen["promedio"],
        "total": resumen["total"],
        "aspectos": {k: v["promedio"] for k, v in resumen["aspectos"].items()},
        "recientes": [
            {
                "puntuacion": r["puntuacion"],
                "comentario": _corto(r["comentario"], MAX_COMENTARIO),
                "mes_visita": r["mes_visita"],
            }
            for r in pagina["items"]
        ],
    }


def capacidad(cuerpo: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "zonas": [
            {
                "zona_codigo": c["zona"]["codigo"],
                "nombre": c["zona"]["nombre"],
                "fecha": c["fecha"],
                "nivel": c["nivel"],
            }
            for c in cuerpo
        ]
    }


def alertas(cuerpo: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "alertas": [
            {
                "nivel": a["nivel"],
                "mensaje": a["mensaje"],
                "zona": _zona(a.get("zona")),
                "zona_codigo": _zona_codigo(a.get("zona")),
                "servicio_id": a.get("servicio_id"),
                "vence": a["fecha_expiracion"],
            }
            for a in cuerpo
        ]
    }
