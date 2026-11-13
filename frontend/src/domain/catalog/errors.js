/** Códigos de error del contrato catalog.yaml (esquema `Error`) más los propios del cliente. */
export const CODIGOS = Object.freeze({
  VALIDACION: 'VALIDACION',
  NO_ENCONTRADO: 'NO_ENCONTRADO',
  SIN_CONEXION: 'SIN_CONEXION',
  RESPUESTA_INVALIDA: 'RESPUESTA_INVALIDA',
  ERROR: 'ERROR',
})

/** Error único del dominio del catálogo: lo lanzan los casos de uso y los adaptadores. */
export class CatalogError extends Error {
  constructor(code, message, { status = 0, correlationId = null } = {}) {
    super(message)
    this.name = 'CatalogError'
    this.code = code
    this.status = status
    this.correlationId = correlationId
  }
}
