import { AssistantError, CODIGOS } from '../../domain/assistant/errors.js'
import { validarMensaje } from '../../domain/assistant/rules.js'
import { assertAssistantGateway } from './ports.js'

/*
 * Caso de uso del asistente (UC14). Mantiene la conversación en curso y se la pasa al servicio en cada
 * mensaje; no sabe de Vue ni de HTTP.
 */
export function createAssistantUseCases({ gateway, session }) {
  assertAssistantGateway(gateway)
  let conversacionId = null
  let epoca = 0 // cambia al empezar de nuevo: una respuesta que llega tarde no debe revivir la conversación anterior

  const mensajes = {
    [CODIGOS.MENSAJE_VACIO]: 'Escribe un mensaje.',
    [CODIGOS.MENSAJE_LARGO]: 'El mensaje es demasiado largo.',
  }

  return {
    conversacionActual: () => conversacionId,

    /** Olvida la conversación: el siguiente mensaje abre una nueva. */
    nuevaConversacion() {
      conversacionId = null
      epoca += 1
    },

    /**
     * UC14 · requiere sesión de Turista y conexión.
     * Si la conversación ya no existe (expiró a las 24 h o es de otro turista), se reenvía el mensaje sin ella.
     * @returns {{ respuesta: string, recomendaciones: {servicioId, nombre, justificacion}[], conversacionReiniciada: boolean }}
     */
    async enviar(texto, { idioma = 'es' } = {}) {
      const v = validarMensaje(texto)
      if (!v.ok) throw new AssistantError(v.codigo, mensajes[v.codigo], { status: 400 })
      if (!session.isAuthenticated()) throw new AssistantError(CODIGOS.NO_AUTENTICADO, 'Inicia sesión para usar el asistente.', { status: 401 })

      const mia = epoca
      let reiniciada = false
      let r
      try {
        r = await gateway.enviarMensaje({ mensaje: v.mensaje, conversacionId, idioma })
      } catch (e) {
        if (!(e instanceof AssistantError) || e.code !== CODIGOS.CONVERSACION_NO_ENCONTRADA || !conversacionId) throw e
        conversacionId = null
        reiniciada = true
        r = await gateway.enviarMensaje({ mensaje: v.mensaje, conversacionId: null, idioma })
      }
      if (mia === epoca) conversacionId = r.conversacion_id
      return {
        respuesta: r.respuesta,
        recomendaciones: r.recomendaciones.map((x) => ({ servicioId: x.servicio_id, nombre: x.nombre, justificacion: x.justificacion_explicabilidad })),
        conversacionReiniciada: reiniciada,
      }
    },
  }
}
