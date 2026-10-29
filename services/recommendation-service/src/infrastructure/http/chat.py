from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from pydantic import BaseModel, ConfigDict, Field

from src.application.responder_mensaje import PeticionChat, ResponderMensaje
from src.infrastructure.http.dependencias import obtener_responder_mensaje
from src.infrastructure.http.errores import PeticionRechazadaError, idioma_de

router = APIRouter(prefix="/api/recommendations", tags=["Chat"])


class ChatPeticion(BaseModel):
    # Lo que no está en el contrato se ignora; en particular, nunca un id de turista.
    model_config = ConfigDict(extra="ignore")

    mensaje: str = Field(min_length=1, max_length=1000)
    conversacion_id: UUID | None = None


class RecomendacionRespuesta(BaseModel):
    servicio_id: UUID
    nombre: str
    justificacion_explicabilidad: str


class ChatRespuesta(BaseModel):
    conversacion_id: UUID
    respuesta: str
    recomendaciones: list[RecomendacionRespuesta]


def turista_autenticado(
    x_usuario_id: Annotated[str | None, Header()] = None,
    x_usuario_rol: Annotated[str | None, Header()] = None,
) -> UUID:
    """La identidad la pone Traefik tras validar el JWT; nunca sale del cuerpo ni del modelo."""
    if not x_usuario_id or not x_usuario_rol:
        raise PeticionRechazadaError(status.HTTP_401_UNAUTHORIZED, "NO_AUTENTICADO")
    try:
        turista_id = UUID(x_usuario_id)
    except ValueError as exc:
        raise PeticionRechazadaError(status.HTTP_401_UNAUTHORIZED, "NO_AUTENTICADO") from exc
    if x_usuario_rol != "Turista":
        raise PeticionRechazadaError(status.HTTP_403_FORBIDDEN, "PROHIBIDO")
    return turista_id


@router.post("/chat", summary="Enviar un mensaje al chatbot (UC14)")
async def chat(
    peticion: ChatPeticion,
    response: Response,
    turista_id: Annotated[UUID, Depends(turista_autenticado)],
    responder: Annotated[ResponderMensaje, Depends(obtener_responder_mensaje)],
    accept_language: Annotated[str | None, Header()] = None,
) -> ChatRespuesta:
    idioma = idioma_de(accept_language)
    resultado = await responder.ejecutar(
        PeticionChat(
            turista_id=turista_id,
            mensaje=peticion.mensaje,
            idioma=idioma,
            conversacion_id=peticion.conversacion_id,
        )
    )
    response.headers["Content-Language"] = idioma
    return ChatRespuesta(
        conversacion_id=resultado.conversacion_id,
        respuesta=resultado.respuesta,
        recomendaciones=[
            RecomendacionRespuesta(
                servicio_id=r.servicio_id,
                nombre=r.nombre,
                justificacion_explicabilidad=r.justificacion,
            )
            for r in resultado.recomendaciones
        ],
    )
