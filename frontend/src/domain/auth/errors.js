/** Códigos de error de iam-service (feature/iam-core) más los propios del cliente. */
export const CODIGOS_AUTH = Object.freeze({
  VALIDACION: 'VALIDACION',
  EMAIL_INVALIDO: 'EMAIL_INVALIDO',
  PASSWORD_INVALIDA: 'PASSWORD_INVALIDA',
  NOMBRE_INVALIDO: 'NOMBRE_INVALIDO',
  HABEAS_DATA_REQUERIDO: 'HABEAS_DATA_REQUERIDO',
  MAYORIA_DE_EDAD_REQUERIDA: 'MAYORIA_DE_EDAD_REQUERIDA',
  ROL_NO_PERMITIDO: 'ROL_NO_PERMITIDO',
  EMAIL_EN_USO: 'EMAIL_EN_USO',
  CREDENCIALES_INVALIDAS: 'CREDENCIALES_INVALIDAS',
  CUENTA_INACTIVA: 'CUENTA_INACTIVA',
  TOKEN_INVALIDO: 'TOKEN_INVALIDO',
  SERVICIO_NO_DISPONIBLE: 'SERVICIO_NO_DISPONIBLE',
  SIN_CONEXION: 'SIN_CONEXION',
  NO_IMPLEMENTADO: 'NO_IMPLEMENTADO',
})

/**
 * Error único del dominio de autenticación. `campos` lista los errores por campo del formulario:
 * [{ campo, mensaje, codigo? }]
 */
export class AuthError extends Error {
  constructor(code, message, { status = 0, campos = [] } = {}) {
    super(message)
    this.name = 'AuthError'
    this.code = code
    this.status = status
    this.campos = campos
  }
}
