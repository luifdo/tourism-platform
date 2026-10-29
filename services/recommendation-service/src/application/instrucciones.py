"""Instrucciones del sistema y la tool con la que el modelo entrega su respuesta final.

La Fase 4 completa las reglas (temas permitidos, equidad, datos como datos, privacidad).
"""

from typing import Literal

from src.application.ports.herramientas import DeclaracionHerramienta

Idioma = Literal["es", "en"]

RESPONDER = "responder_al_turista"

DECLARACION_RESPONDER = DeclaracionHerramienta(
    nombre=RESPONDER,
    descripcion=(
        "Entrega la respuesta final al turista. Llámala una sola vez, al terminar, después de "
        "consultar lo necesario. Cada recomendación debe ser un servicio que salió de otra tool "
        "y llevar su justificación basada en los datos consultados."
    ),
    parametros={
        "type": "object",
        "properties": {
            "respuesta": {
                "type": "string",
                "description": "Texto para el turista, en su idioma.",
            },
            "recomendaciones": {
                "type": "array",
                "description": "Servicios recomendados; vacía si no recomiendas ninguno.",
                "items": {
                    "type": "object",
                    "properties": {
                        "servicio_id": {"type": "string", "format": "uuid"},
                        "nombre": {"type": "string"},
                        "justificacion": {
                            "type": "string",
                            "description": "Por qué se recomienda, según los datos consultados.",
                        },
                    },
                    "required": ["servicio_id", "nombre", "justificacion"],
                },
            },
        },
        "required": ["respuesta", "recomendaciones"],
    },
)

_NOMBRE_IDIOMA = {"es": "español", "en": "inglés (English)"}


def instrucciones(idioma: Idioma) -> str:
    return (
        "Eres el asistente turístico de la Plataforma Digital de Turismo de Santa Marta "
        "(Colombia). Ayudas al turista a descubrir atractivos, actividades y servicios de la "
        "plataforma y le recomiendas opciones explicando por qué.\n"
        "- Usa las tools para obtener datos reales; no inventes servicios, precios, cupos ni "
        "reseñas.\n"
        "- Solo puedes recomendar servicios que hayan salido de una tool, cada uno con su "
        "justificación.\n"
        "- Prefiere zonas con presión de capacidad de carga BAJA y advierte sobre las alertas "
        "oficiales vigentes.\n"
        "- Eres de solo lectura: no puedes reservar, cancelar ni modificar nada; indica al "
        "turista que abra la ficha del servicio en la plataforma para reservar.\n"
        f"- Responde en {_NOMBRE_IDIOMA[idioma]}.\n"
        f"- Termina siempre llamando a `{RESPONDER}`."
    )


MENSAJE_LIMITE = {
    "es": (
        "No pude completar tu consulta con la información disponible. ¿Puedes hacerla más "
        "concreta? Por ejemplo, indica la zona, la fecha o el tipo de actividad."
    ),
    "en": (
        "I couldn't complete your request with the available information. Could you make it "
        "more specific? For example, tell me the area, the date or the kind of activity."
    ),
}

MENSAJE_VACIO = {
    "es": "No tengo una respuesta para eso. ¿Puedes reformular tu pregunta?",
    "en": "I don't have an answer for that. Could you rephrase your question?",
}
