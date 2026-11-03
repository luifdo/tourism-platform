/** Códigos de error del contrato recommendation.yaml (esquema `Error`) más los propios del cliente. */
export const CODIGOS = Object.freeze({
  // del servicio
  VALIDACION: 'VALIDACION',
  NO_AUTENTICADO: 'NO_AUTENTICADO',
  PROHIBIDO: 'PROHIBIDO',
  CONVERSACION_NO_ENCONTRADA: 'CONVERSACION_NO_ENCONTRADA',
  DEMASIADAS_SOLICITUDES: 'DEMASIADAS_SOLICITUDES',
  ASISTENTE_NO_DISPONIBLE: 'ASISTENTE_NO_DISPONIBLE',
  // del cliente
  MENSAJE_VACIO: 'MENSAJE_VACIO',
  MENSAJE_LARGO: 'MENSAJE_LARGO',
  SIN_CONEXION: 'SIN_CONEXION',
  TIEMPO_AGOTADO: 'TIEMPO_AGOTADO',
  RESPUESTA_INVALIDA: 'RESPUESTA_INVALIDA',
  ERROR: 'ERROR',
})

/** Error único del dominio del asistente: lo lanzan los casos de uso y los adaptadores. */
export class AssistantError extends Error {
  constructor(code, message, { status = 0, correlationId = null, retryAfter = null } = {}) {
    super(message)
    this.name = 'AssistantError'
    this.code = code
    this.status = status
    this.correlationId = correlationId
    this.retryAfter = retryAfter // segundos, si el servicio los indica
  }
}
