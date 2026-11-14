"""Datos fijos de Santa Marta para el mock de catalog, booking y review.

Están pensados para ejercitar las reglas del chatbot: zonas con distinta presión de
capacidad (Tayrona ALTO, Minca y Palomino BAJO), alertas oficiales activas y un turista
con historial de reservas.
"""

from uuid import UUID

# Turista con reservas en el historial; cualquier otro id tiene el historial vacío.
TURISTA_CON_HISTORIAL = UUID("7c0e7a52-6f4b-4d65-9a3e-2f1d8b0c4e11")

ZONAS = {
    "taganga": {"nombre": "Taganga", "nivel": "MEDIO", "indice": 0.72},
    "minca": {"nombre": "Minca", "nivel": "BAJO", "indice": 0.35},
    "tayrona": {"nombre": "Parque Tayrona", "nivel": "ALTO", "indice": 0.93},
    "palomino": {"nombre": "Palomino", "nivel": "BAJO", "indice": 0.28},
    "centro-historico": {"nombre": "Centro Histórico", "nivel": "MEDIO", "indice": 0.64},
}

ETIQUETAS = {
    "es": {
        "BAJO": "Bajo",
        "MEDIO": "Medio",
        "ALTO": "Alto",
        "INFORMATIVA": "Informativa",
        "PREVENTIVA": "Preventiva",
        "CRITICA": "Crítica",
        "POR_PERSONA": "por persona",
        "POR_NOCHE": "por noche",
    },
    "en": {
        "BAJO": "Low",
        "MEDIO": "Medium",
        "ALTO": "High",
        "INFORMATIVA": "Informational",
        "PREVENTIVA": "Preventive",
        "CRITICA": "Critical",
        "POR_PERSONA": "per person",
        "POR_NOCHE": "per night",
    },
}

SERVICIOS = [
    {
        "id": UUID("3f2a1b6c-1d4e-4f8a-9b2c-5e6d7f8a9b01"),
        "nombre": "Buceo recreativo en Taganga",
        "descripcion": "Inmersión guiada de dos tanques en los arrecifes de Taganga, con equipo incluido.",
        "tipo": "DEPORTE_ACUATICO",
        "categoria": "AVENTURA",
        "zona": "taganga",
        "ubicacion": {"lat": 11.2675, "lon": -74.1906},
        "tarifa_base": 180000,
        "unidad_tarifa": "POR_PERSONA",
        "aforo": 12,
        "prestador": "Taganga Dive Center S.A.S.",
        "aviso_pagos": None,
    },
    {
        "id": UUID("3f2a1b6c-1d4e-4f8a-9b2c-5e6d7f8a9b02"),
        "nombre": "Tour de café en Minca",
        "descripcion": "Recorrido por una finca cafetera de la Sierra Nevada con cata de café de origen.",
        "tipo": "TOUR_CULTURAL",
        "categoria": "CULTURA",
        "zona": "minca",
        "ubicacion": {"lat": 11.1433, "lon": -74.1167},
        "tarifa_base": 120000,
        "unidad_tarifa": "POR_PERSONA",
        "aforo": 20,
        "prestador": "Finca La Victoria",
        "aviso_pagos": "Lleva efectivo: no hay señal de internet y el cajero más cercano está en Santa Marta.",
    },
    {
        "id": UUID("3f2a1b6c-1d4e-4f8a-9b2c-5e6d7f8a9b03"),
        "nombre": "Avistamiento de aves en Minca",
        "descripcion": "Caminata al amanecer con guía local para observar aves endémicas de la Sierra Nevada.",
        "tipo": "AVISTAMIENTO",
        "categoria": "NATURALEZA",
        "zona": "minca",
        "ubicacion": {"lat": 11.1401, "lon": -74.1102},
        "tarifa_base": 150000,
        "unidad_tarifa": "POR_PERSONA",
        "aforo": 10,
        "prestador": "Aves de la Sierra",
        "aviso_pagos": None,
    },
    {
        "id": UUID("3f2a1b6c-1d4e-4f8a-9b2c-5e6d7f8a9b04"),
        "nombre": "Entrada al Parque Tayrona",
        "descripcion": "Ingreso al Parque Nacional Natural Tayrona por el sector de El Zaino.",
        "tipo": "RESERVA_PARQUE",
        "categoria": "NATURALEZA",
        "zona": "tayrona",
        "ubicacion": {"lat": 11.2869, "lon": -73.9286},
        "tarifa_base": 85000,
        "unidad_tarifa": "POR_PERSONA",
        "aforo": 300,
        "prestador": "Concesión Tayrona",
        "aviso_pagos": None,
    },
    {
        "id": UUID("3f2a1b6c-1d4e-4f8a-9b2c-5e6d7f8a9b05"),
        "nombre": "Ecohotel frente al mar en Palomino",
        "descripcion": "Cabañas de madera a pocos pasos de la playa y de la desembocadura del río Palomino.",
        "tipo": "POSADA_ECOHOTEL",
        "categoria": "ALOJAMIENTO",
        "zona": "palomino",
        "ubicacion": {"lat": 11.2475, "lon": -73.5631},
        "tarifa_base": 320000,
        "unidad_tarifa": "POR_NOCHE",
        "aforo": 16,
        "prestador": "Ecohotel Palomino",
        "aviso_pagos": None,
    },
    {
        "id": UUID("3f2a1b6c-1d4e-4f8a-9b2c-5e6d7f8a9b06"),
        "nombre": "Tubing por el río Palomino",
        "descripcion": "Descenso en neumático por el río Palomino hasta el mar, con transporte de subida.",
        "tipo": "DEPORTE_ACUATICO",
        "categoria": "AVENTURA",
        "zona": "palomino",
        "ubicacion": {"lat": 11.2512, "lon": -73.5702},
        "tarifa_base": 60000,
        "unidad_tarifa": "POR_PERSONA",
        "aforo": 40,
        "prestador": "Río Aventura",
        "aviso_pagos": None,
    },
    {
        "id": UUID("3f2a1b6c-1d4e-4f8a-9b2c-5e6d7f8a9b07"),
        "nombre": "Cocina caribeña en el Centro Histórico",
        "descripcion": "Restaurante de cocina samaria tradicional a una cuadra del Parque de los Novios.",
        "tipo": "RESTAURANTE",
        "categoria": "GASTRONOMIA",
        "zona": "centro-historico",
        "ubicacion": {"lat": 11.2420, "lon": -74.2130},
        "tarifa_base": 70000,
        "unidad_tarifa": "POR_PERSONA",
        "aforo": 60,
        "prestador": "Sabor Samario",
        "aviso_pagos": None,
    },
]

SERVICIOS_POR_ID = {s["id"]: s for s in SERVICIOS}

ALERTAS = [
    {
        "id": UUID("a1e2f3a4-0000-4000-8000-000000000001"),
        "nivel": "CRITICA",
        "mensaje": "El sector de Cabo San Juan supera la capacidad de carga: se recomienda visitar otras playas.",
        "zona": "tayrona",
        "servicio_id": None,
        "fecha_expiracion": "2026-12-31T23:59:00-05:00",
    },
    {
        "id": UUID("a1e2f3a4-0000-4000-8000-000000000002"),
        "nivel": "INFORMATIVA",
        "mensaje": "Lluvias en la tarde: los caminos hacia las fincas pueden estar embarrados.",
        "zona": "minca",
        "servicio_id": None,
        "fecha_expiracion": "2026-11-30T18:00:00-05:00",
    },
]

# (puntuación, comentario, mes de la visita, día de creación)
RESENAS = {
    SERVICIOS[0]["id"]: [
        (5, "Los instructores muy pacientes y el arrecife precioso.", "2026-09", 12),
        (4, "Buena experiencia, aunque el bote salió tarde.", "2026-08", 3),
        (5, None, "2026-07", 20),
    ],
    SERVICIOS[1]["id"]: [
        (5, "Aprendimos todo el proceso del café, la vista es increíble.", "2026-10", 5),
        (5, "Muy recomendado, lleven efectivo.", "2026-09", 18),
    ],
    SERVICIOS[2]["id"]: [(5, "Vimos más de veinte especies.", "2026-10", 2)],
    SERVICIOS[3]["id"]: [
        (5, "Paisajes únicos.", "2026-08", 9),
        (4, "Mucha gente en Cabo San Juan.", "2026-09", 14),
    ],
    SERVICIOS[4]["id"]: [(4, "Tranquilo y cerca del río.", "2026-07", 25)],
}

# (servicio, fecha, personas, estado)
RESERVAS_TURISTA = [
    (SERVICIOS[1]["id"], "2026-09-14", 2, "FINALIZADA"),
    (SERVICIOS[0]["id"], "2026-11-08", 2, "CONFIRMADA"),
]
