from fastapi import Request

from src.application.verificar_salud import VerificarSalud


def obtener_verificar_salud(request: Request) -> VerificarSalud:
    return request.app.state.verificar_salud
