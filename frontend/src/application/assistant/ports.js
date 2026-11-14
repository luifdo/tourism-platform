/*
 * PUERTOS del asistente (UC14).
 *
 * AssistantGateway  (puerto de salida; hoy lo implementa recommendation-service vía el Gateway)
 *   enviarMensaje({ mensaje, conversacionId, idioma })
 *     -> { conversacion_id, respuesta, recomendaciones: [{ servicio_id, nombre, justificacion_explicabilidad }] }
 *   `conversacionId` es null en el primer mensaje. Los errores se lanzan como AssistantError.
 *
 * Session (puerto de salida)  isAuthenticated() -> boolean
 */
export const ASSISTANT_GATEWAY_METHODS = Object.freeze(['enviarMensaje'])

export function assertAssistantGateway(gateway) {
  const faltan = ASSISTANT_GATEWAY_METHODS.filter((m) => typeof gateway?.[m] !== 'function')
  if (faltan.length) throw new TypeError(`El adaptador del asistente no implementa el puerto AssistantGateway: faltan ${faltan.join(', ')}`)
  return gateway
}
