/** Códigos de error del contrato booking.yaml (esquema `Error`) más los propios del cliente. */
export const CODIGOS = Object.freeze({
  VALIDACION: 'VALIDACION',
  NO_AUTENTICADO: 'NO_AUTENTICADO',
  ROL_NO_PERMITIDO: 'ROL_NO_PERMITIDO',
  NO_ENCONTRADO: 'NO_ENCONTRADO',
  CUPOS_INSUFICIENTES: 'CUPOS_INSUFICIENTES',
  DIA_NO_DISPONIBLE: 'DIA_NO_DISPONIBLE',
  RESERVA_DUPLICADA: 'RESERVA_DUPLICADA',
  TRANSICION_INVALIDA: 'TRANSICION_INVALIDA',
  FUERA_DE_PLAZO: 'FUERA_DE_PLAZO',
  VERSION_DISTINTA: 'VERSION_DISTINTA',
  FALTA_IF_MATCH: 'FALTA_IF_MATCH',
  SIN_CONEXION: 'SIN_CONEXION',
})

/** Error único del dominio de reservas: lo lanzan los casos de uso y los adaptadores. */
export class BookingError extends Error {
  constructor(code, message, { status = 0, correlationId = null } = {}) {
    super(message)
    this.name = 'BookingError'
    this.code = code
    this.status = status
    this.correlationId = correlationId
  }
}
