from fastapi import Request

from src.application.responder_mensaje import ResponderMensaje
from src.application.verificar_salud import VerificarSalud


def obtener_verificar_salud(request: Request) -> VerificarSalud:
    return request.app.state.verificar_salud


def obtener_responder_mensaje(request: Request) -> ResponderMensaje:
    return request.app.state.responder_mensaje
