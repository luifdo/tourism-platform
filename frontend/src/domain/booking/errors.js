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
  PLAZO_VENCIDO: 'PLAZO_VENCIDO',
  // Idempotency-Key (INTEGRACION.md §2.3): se reintenta con la MISMA clave
  PETICION_EN_PROCESO: 'PETICION_EN_PROCESO',
  IDEMPOTENCIA_NO_DISPONIBLE: 'IDEMPOTENCIA_NO_DISPONIBLE',
  // Calendario del prestador
  DIA_EXISTENTE: 'DIA_EXISTENTE',
  CUPOS_COMPROMETIDOS: 'CUPOS_COMPROMETIDOS',
  SUPERA_AFORO: 'SUPERA_AFORO',
  // Propios del cliente (validación antes de llamar al servidor)
  MOTIVO_INVALIDO: 'MOTIVO_INVALIDO',
  SIN_CONEXION: 'SIN_CONEXION',
})

/** Error único del dominio de reservas: lo lanzan los casos de uso y los adaptadores. */
export class BookingError extends Error {
  /** `data`: el cuerpo del error; en un 409 VERSION_DISTINTA trae `version_actual` y `actual` (el registro como está ahora). */
  constructor(code, message, { status = 0, correlationId = null, data = null } = {}) {
    super(message)
    this.name = 'BookingError'
    this.code = code
    this.status = status
    this.correlationId = correlationId
    this.data = data
  }
}
