import { AssistantError, CODIGOS } from '../../domain/assistant/errors.js'
import { ESPERA_MAXIMA_MS } from '../../domain/assistant/rules.js'

const CONOCIDOS = new Set(Object.values(CODIGOS))
// Si la respuesta de error no trae un código del contrato (por ejemplo el 401 de ForwardAuth o un 502 de Traefik)
const CODIGO_POR_ESTADO = { 400: CODIGOS.VALIDACION, 401: CODIGOS.NO_AUTENTICADO, 403: CODIGOS.PROHIBIDO, 429: CODIGOS.DEMASIADAS_SOLICITUDES, 502: CODIGOS.ASISTENTE_NO_DISPONIBLE, 503: CODIGOS.ASISTENTE_NO_DISPONIBLE, 504: CODIGOS.ASISTENTE_NO_DISPONIBLE }
// Un 404 sin código NO es "conversación no encontrada": puede ser una ruta que el gateway no tiene.

const esRecomendacion = (r) => r && typeof r.servicio_id === 'string' && typeof r.nombre === 'string' && typeof r.justificacion_explicabilidad === 'string'

/**
 * Adaptador HTTP del puerto AssistantGateway: habla con el recommendation-service a través del Gateway
 * (Traefik), siguiendo contracts/openapi/recommendation.yaml.
 */
export function createHttpAssistantGateway({ baseUrl = '/api/recommendations', fetchFn = (...a) => fetch(...a), timeoutMs = ESPERA_MAXIMA_MS } = {}) {
  return {
    async enviarMensaje({ mensaje, conversacionId, idioma = 'es' }) {
      const headers = { Accept: 'application/json', 'Content-Type': 'application/json', 'Accept-Language': idioma }

      const control = new AbortController()
      let agotado = false
      const temporizador = setTimeout(() => { agotado = true; control.abort() }, timeoutMs)
      try {
        let res
        try {
          res = await fetchFn(`${baseUrl}/chat`, {
            method: 'POST', headers, signal: control.signal,
            body: JSON.stringify(conversacionId ? { mensaje, conversacion_id: conversacionId } : { mensaje }),
          })
        } catch {
          throw agotado
            ? new AssistantError(CODIGOS.TIEMPO_AGOTADO, 'El asistente tardó demasiado en responder.')
            : new AssistantError(CODIGOS.SIN_CONEXION, 'No hay conexión con el servidor.')
        }
        const data = await res.json().catch(() => null)

        if (!res.ok) {
          const delServicio = data?.error ?? data?.code // recommendation usa `error`; iam (ForwardAuth) usa `code`
          const code = CONOCIDOS.has(delServicio) ? delServicio : CODIGO_POR_ESTADO[res.status] ?? CODIGOS.ERROR
          const mensajeServidor = [data?.message, data?.detail].find((m) => typeof m === 'string') ?? res.statusText
          const espera = Number(res.headers?.get?.('Retry-After'))
          throw new AssistantError(code, mensajeServidor, { status: res.status, correlationId: data?.correlation_id ?? null, retryAfter: espera > 0 ? espera : null })
        }
        // Una ruta que el gateway no tiene cae en el frontend y devuelve su HTML con 200: no es una respuesta del asistente.
        if (typeof data?.conversacion_id !== 'string' || typeof data?.respuesta !== 'string' || !Array.isArray(data?.recomendaciones))
          throw new AssistantError(CODIGOS.RESPUESTA_INVALIDA, 'La respuesta del asistente no tiene el formato esperado.', { status: res.status })
        return { ...data, recomendaciones: data.recomendaciones.filter(esRecomendacion) }
      } finally {
        clearTimeout(temporizador)
      }
    },
  }
}
