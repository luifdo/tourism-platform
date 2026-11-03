import { reactive, readonly } from 'vue'
import { assistantUseCases } from '../composition'
import { CODIGOS } from '../domain/assistant/errors'
import { validarMensaje } from '../domain/assistant/rules'

/*
 * Estado reactivo del chat para la interfaz. La lógica (validar, conversación, reintento si venció) está en
 * el caso de uso; aquí solo se guardan los mensajes que se pintan. Vive en memoria: el texto de las
 * conversaciones no se guarda en el dispositivo (Ley 1581).
 */
const estado = reactive({
  mensajes: [], // { id, rol: 'usuario' | 'asistente' | 'nota', texto, recomendaciones? }
  enviando: false,
  error: null, // { codigo, texto, retryAfter } · `texto` es lo que se reenvía con "Reintentar"
})
let generacion = 0 // sube al empezar de nuevo: lo que responda una consulta anterior se descarta
let secuencia = 0
const mensaje = (rol, datos) => ({ id: ++secuencia, rol, ...datos })

// Errores tras los que reenviar el mismo mensaje no cambia nada
const SIN_REINTENTO = new Set([CODIGOS.NO_AUTENTICADO, CODIGOS.PROHIBIDO, CODIGOS.VALIDACION, CODIGOS.MENSAJE_VACIO, CODIGOS.MENSAJE_LARGO])

async function enviar(texto, { idioma = 'es', alExpirar, reintento = false } = {}) {
  if (estado.enviando) return false
  const v = validarMensaje(texto)
  if (!v.ok) { estado.error = { codigo: v.codigo, texto: null, retryAfter: null }; return false }

  const mia = generacion
  if (!reintento) estado.mensajes.push(mensaje('usuario', { texto: v.mensaje }))
  estado.error = null
  estado.enviando = true
  try {
    const r = await assistantUseCases.enviar(v.mensaje, { idioma })
    if (mia !== generacion) return false
    if (r.conversacionReiniciada) estado.mensajes.push(mensaje('nota', { clave: 'newConversationNote' }))
    estado.mensajes.push(mensaje('asistente', { texto: r.respuesta, recomendaciones: r.recomendaciones }))
    return true
  } catch (e) {
    if (mia !== generacion) return false
    estado.error = { codigo: e.code ?? CODIGOS.ERROR, texto: v.mensaje, retryAfter: e.retryAfter ?? null }
    if (e.code === CODIGOS.NO_AUTENTICADO) alExpirar?.() // el token venció o no sirve: la interfaz pide ingresar de nuevo
    return false
  } finally {
    if (mia === generacion) estado.enviando = false
  }
}

/** Vuelve a mandar el último mensaje que falló, sin repetirlo en la conversación. */
const reintentar = (opciones) => (estado.error?.texto ? enviar(estado.error.texto, { ...opciones, reintento: true }) : false)

/** Borra la conversación (nueva conversación, o cambio/cierre de sesión). */
function reiniciar() {
  generacion += 1
  assistantUseCases.nuevaConversacion()
  estado.mensajes.splice(0)
  estado.enviando = false
  estado.error = null
}

export const puedeReintentar = (error) => !!error?.texto && !SIN_REINTENTO.has(error.codigo)

export function useAssistant() {
  return { estado: readonly(estado), enviar, reintentar, reiniciar }
}
