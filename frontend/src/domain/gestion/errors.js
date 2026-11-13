/** Códigos de error de las pantallas de gestión (perfil, oferta, reseñas, admin, entidad). Son estables: la interfaz los traduce. */
export const CODIGOS_GESTION = Object.freeze({
  SIN_CONEXION: 'SIN_CONEXION',
  NO_AUTENTICADO: 'NO_AUTENTICADO',
  ROL_INSUFICIENTE: 'ROL_INSUFICIENTE',
  VALIDACION: 'VALIDACION',
  NO_ENCONTRADO: 'NO_ENCONTRADO',
  VERSION_DISTINTA: 'VERSION_DISTINTA',
  SERVICIO_NO_DISPONIBLE: 'SERVICIO_NO_DISPONIBLE',
  ERROR: 'ERROR',
})

/**
 * Error de un servicio del backend traducido a algo que la interfaz entiende.
 * `code`: el código del servicio (p. ej. YA_RESENADO, DOCUMENTO_APROBADO) o uno de CODIGOS_GESTION;
 * `status`: HTTP; `campos`: [{ campo, mensaje }] si el servicio detalló qué campo falló; `data`: cuerpo completo.
 */
export class GestionError extends Error {
  constructor(code, message, { status, campos = [], data = null, correlationId } = {}) {
    super(message)
    this.name = 'GestionError'
    this.code = code
    this.status = status
    this.campos = campos
    this.data = data
    this.correlationId = correlationId
  }
}
