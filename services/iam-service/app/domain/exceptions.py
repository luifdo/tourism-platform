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


class AutogestionNoPermitidaError(DominioError):
    """C-29: un Admin no puede cambiar su propio rol ni desactivarse a sí mismo."""

    code = "AUTOGESTION_NO_PERMITIDA"
    default_message = "No puede cambiar su propio rol ni desactivar su propia cuenta."


class UltimoAdminError(DominioError):
    """C-29: la plataforma no puede quedarse sin Admins activos."""

    code = "ULTIMO_ADMIN"
    default_message = "No se puede dejar la plataforma sin administradores activos."


class CuentaSuprimidaError(DominioError):
    """C-27: la cuenta ya no tiene datos personales; no se reactiva ni cambia de rol."""

    code = "CUENTA_SUPRIMIDA"
    default_message = "Los datos de esta cuenta fueron suprimidos."


class VersionConflictoError(DominioError):
    """C-49: el perfil cambió desde que el cliente lo leyó (If-Match)."""

    code = "VERSION_CONFLICTO"
    default_message = "El perfil cambió desde la última vez que se consultó."


class TokenRecuperacionInvalidoError(DominioError):
    """C-28: 400, no 401: no es una sesión vencida. El código es el que espera ResetView.vue."""

    code = "TOKEN_INVALIDO"
    default_message = "El enlace de recuperación no es válido, expiró o ya se usó."


class NoEsPrestadorError(DominioError):
    code = "NO_ES_PRESTADOR"
    default_message = "La cuenta no tiene el rol Prestador."


class DocumentoNoEncontradoError(DominioError):
    code = "DOCUMENTO_NO_ENCONTRADO"
    default_message = "El documento no existe."


class DocumentoAprobadoError(DominioError):
    """C-30: un documento vigente aprobado no se reemplaza (la renovación queda fuera, C-45)."""

    code = "DOCUMENTO_APROBADO"
    default_message = "El documento vigente de ese tipo ya fue aprobado y no se puede reemplazar."


class DocumentosIncompletosError(DominioError):
    code = "DOCUMENTOS_INCOMPLETOS"
    default_message = "El prestador no tiene cargados el RNT y el RUT."


class DocumentoYaRevisadoError(DominioError):
    code = "DOCUMENTO_YA_REVISADO"
    default_message = "El documento ya fue revisado; el prestador debe cargar uno nuevo."


class ArchivoDemasiadoGrandeError(DominioError):
    code = "ARCHIVO_DEMASIADO_GRANDE"
    default_message = "El archivo supera los 5 MB."


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


class ServicioOcupadoError(DominioError):
    code = "SERVICIO_OCUPADO"
    default_message = "El servicio está ocupado. Intente de nuevo en unos segundos."


class DominioValidationError(DominioError):
    code = "VALIDACION_FALLIDA"
    default_message = "Los datos no cumplen las reglas del dominio."


class PasswordInvalidaError(DominioValidationError):
    code = "PASSWORD_INVALIDA"
    default_message = (
        "La contraseña debe tener entre 8 y 128 caracteres, con al menos una letra y un número."
    )


class PasswordActualIncorrectaError(DominioValidationError):
    """C-52: 422, no 401, para que la PWA no lo confunda con una sesión vencida."""

    code = "PASSWORD_ACTUAL_INCORRECTA"
    default_message = "La contraseña actual no es correcta."


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


class RangoFechasInvalidoError(DominioValidationError):
    code = "RANGO_FECHAS_INVALIDO"
    default_message = "La fecha 'desde' debe ser anterior a 'hasta'."


class TipoArchivoNoPermitidoError(DominioValidationError):
    code = "TIPO_ARCHIVO_NO_PERMITIDO"
    default_message = "Solo se aceptan archivos PDF, JPG o PNG."


class RazonSocialInvalidaError(DominioValidationError):
    code = "RAZON_SOCIAL_INVALIDA"
    default_message = (
        "La razón social es obligatoria con el RUT y debe tener entre 2 y 200 caracteres."
    )


class RolNoPermitidoError(DominioValidationError):
    code = "ROL_NO_PERMITIDO"
    default_message = "Solo se pueden autorregistrar cuentas de Turista o Prestador."
