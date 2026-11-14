import { AssistantError, CODIGOS } from '../../domain/assistant/errors.js'
import { validarMensaje } from '../../domain/assistant/rules.js'
import { responderDemo } from './demoRespuestas.js'

const VIDA_CONVERSACION_MS = 24 * 60 * 60 * 1000 // el servicio la guarda 24 horas

const uuid = () => globalThis.crypto?.randomUUID?.() ?? 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => { const r = (Math.random() * 16) | 0; return (c === 'x' ? r : (r & 3) | 8).toString(16) })

/**
 * Adaptador simulado del puerto AssistantGateway: se comporta como el contrato recommendation.yaml
 * (identidad, conversaciones de 24 h que son de un solo turista, límite de mensajes, 404 y 429) para
 * poder desarrollar y probar la interfaz sin Gateway ni proveedor de IA.
 */
export function createMockAssistantGateway({
  clock = { now: () => new Date() },
  turistaId = () => null,
  esperaMs = 900,
  limite = { mensajes: 10, ventanaMs: 5 * 60 * 1000 }, // como el servicio: 10 mensajes cada 5 minutos por turista
  newId = uuid,
  sleep = (ms) => new Promise((r) => setTimeout(r, ms)),
  responder = responderDemo,
} = {}) {
  const conversaciones = new Map() // id -> { turista, creada }
  const envios = new Map() // turista -> [instantes en ms]

  return {
    async enviarMensaje({ mensaje, conversacionId, idioma = 'es' }) {
      const turista = turistaId()
      if (!turista) throw new AssistantError(CODIGOS.NO_AUTENTICADO, 'Falta la identidad del turista.', { status: 401 })
      const v = validarMensaje(mensaje)
      if (!v.ok) throw new AssistantError(CODIGOS.VALIDACION, 'Mensaje inválido.', { status: 400 })

      const ahora = clock.now().getTime()
      if (conversacionId) {
        const c = conversaciones.get(conversacionId)
        // Igual que el servicio: no existe, expiró o es de otro turista -> la misma respuesta
        if (!c || c.turista !== turista || ahora - c.creada > VIDA_CONVERSACION_MS)
          throw new AssistantError(CODIGOS.CONVERSACION_NO_ENCONTRADA, 'La conversación no existe o expiró.', { status: 404 })
      }

      const recientes = (envios.get(turista) ?? []).filter((t) => ahora - t < limite.ventanaMs)
      if (recientes.length >= limite.mensajes) {
        envios.set(turista, recientes)
        throw new AssistantError(CODIGOS.DEMASIADAS_SOLICITUDES, 'Superaste el límite de mensajes.', {
          status: 429, retryAfter: Math.ceil((recientes[0] + limite.ventanaMs - ahora) / 1000),
        })
      }
      envios.set(turista, [...recientes, ahora])

      await sleep(esperaMs) // el modelo real tarda segundos
      const id = conversacionId ?? newId()
      if (!conversacionId) conversaciones.set(id, { turista, creada: ahora })
      const { respuesta, recomendaciones } = responder(v.mensaje, idioma)
      return { conversacion_id: id, respuesta, recomendaciones }
    },
  }
}
