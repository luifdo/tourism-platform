import uuid
from typing import Literal

# Motivo interno de un 401: va a la bitácora, nunca a la respuesta.
MotivoRechazo = Literal["sin_token", "invalido", "expirado", "revocado", "tipo"]


class DominioError(Exception):
    """Error de negocio. La capa HTTP lo traduce a {"detail": message, "code": code}."""

    code: str = "ERROR_DE_DOMINIO"
    default_message: str = "Error de dominio."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class UsuarioYaExisteError(DominioError):
    code = "EMAIL_EN_USO"
    default_message = "Ya existe una cuenta registrada con ese correo electrónico."


class UsuarioNoEncontradoError(DominioError):
    code = "USUARIO_NO_ENCONTRADO"
    default_message = "El usuario no existe."


class CredencialesInvalidasError(DominioError):
    """Mismo mensaje si el correo no existe o la contraseña no coincide (no revela cuentas)."""

    code = "CREDENCIALES_INVALIDAS"
    default_message = "Correo o contraseña incorrectos."


class CuentaInactivaError(DominioError):
    code = "CUENTA_INACTIVA"
    default_message = "La cuenta está desactivada. Contacte al administrador."


class TokenInvalidoError(DominioError):
    """El cliente siempre recibe el mismo mensaje; motivo y usuario_id son solo para auditar.

    usuario_id solo se conoce si la firma del token fue válida.
    """

    code = "TOKEN_INVALIDO"
    default_message = "El token no es válido, expiró o fue revocado."

    def __init__(
        self,
        message: str | None = None,
        *,
        motivo: MotivoRechazo | None = None,
        usuario_id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(message)
        self.motivo = motivo
        self.usuario_id = usuario_id


class RolInsuficienteError(DominioError):
    code = "ROL_INSUFICIENTE"
    default_message = "No tiene permisos para realizar esta acción."


class ServicioNoDisponibleError(DominioError):
    code = "SERVICIO_NO_DISPONIBLE"
    default_message = "El servicio no está disponible temporalmente. Intente de nuevo."


class DominioValidationError(DominioError):
    code = "VALIDACION_FALLIDA"
    default_message = "Los datos no cumplen las reglas del dominio."


class PasswordInvalidaError(DominioValidationError):
    code = "PASSWORD_INVALIDA"
    default_message = (
        "La contraseña debe tener entre 8 y 128 caracteres, con al menos una letra y un número."
    )


class EmailInvalidoError(DominioValidationError):
    code = "EMAIL_INVALIDO"
    default_message = "El correo electrónico no es válido."


class NombreInvalidoError(DominioValidationError):
    code = "NOMBRE_INVALIDO"
    default_message = "El nombre completo debe tener entre 2 y 150 caracteres."


class HabeasDataNoAceptadoError(DominioValidationError):
    code = "HABEAS_DATA_REQUERIDO"
    default_message = (
        "Debe aceptar la política de tratamiento de datos personales (Ley 1581 de 2012)."
    )


class MenorDeEdadError(DominioValidationError):
    code = "MAYORIA_DE_EDAD_REQUERIDA"
    default_message = "Debe ser mayor de edad para registrarse."


class RolNoPermitidoError(DominioValidationError):
    code = "ROL_NO_PERMITIDO"
    default_message = "Solo se pueden autorregistrar cuentas de Turista o Prestador."
