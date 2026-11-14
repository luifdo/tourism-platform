import { CODIGOS } from './errors.js'

/** Máximo de caracteres de un mensaje (contrato: ChatPeticion.mensaje). */
export const MAX_MENSAJE = 1000

/**
 * Cuánto se espera la respuesta. El modelo tarda de 3 a 15 s, el servicio corta a los 45 s con un 503
 * y el gateway espera 60 s: el cliente debe esperar al menos 50 s para ver ese 503 en vez de abandonar antes.
 */
export const ESPERA_MAXIMA_MS = 50_000

/** El chatbot es de solo lectura y solo atiende a turistas (contrato: 403 PROHIBIDO para otros roles). */
export const ROL_ASISTENTE = 'Turista'
export const puedeUsarAsistente = (rol) => rol === ROL_ASISTENTE

/** Largo en caracteres reales (un emoji cuenta uno), como lo cuenta el servicio. */
export const largo = (texto) => [...texto].length

/** Quita los espacios de los bordes y comprueba lo que el contrato exige del mensaje. */
export function validarMensaje(texto) {
  const mensaje = String(texto ?? '').trim()
  if (!mensaje) return { ok: false, codigo: CODIGOS.MENSAJE_VACIO }
  if (largo(mensaje) > MAX_MENSAJE) return { ok: false, codigo: CODIGOS.MENSAJE_LARGO }
  return { ok: true, mensaje }
}
