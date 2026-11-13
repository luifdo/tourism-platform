import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHttpAssistantGateway } from '../../src/infrastructure/assistant/httpAssistantGateway.js'
import { assertAssistantGateway } from '../../src/application/assistant/ports.js'
import { AssistantError } from '../../src/domain/assistant/errors.js'

const respuesta = (cuerpo, { status = 200, retryAfter } = {}) => ({
  ok: status < 400, status, statusText: 'x',
  json: async () => { if (cuerpo === undefined) throw new SyntaxError('no es JSON'); return cuerpo },
  headers: { get: (h) => (h.toLowerCase() === 'retry-after' ? retryAfter ?? null : null) },
})
const buena = { conversacion_id: 'c-1', respuesta: 'Hola', recomendaciones: [{ servicio_id: 's-1', nombre: 'N', justificacion_explicabilidad: 'J' }] }
const crear = (fetchFn, extra = {}) => createHttpAssistantGateway({ baseUrl: '/api/recommendations', fetchFn, ...extra })
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }

afterEach(() => vi.useRealTimers())

describe('adaptador HTTP del asistente', () => {
  it('implementa el puerto AssistantGateway', () => {
    expect(assertAssistantGateway(crear(vi.fn()))).toBeTruthy()
  })

  it('envía el mensaje a /chat con el idioma, sin conversación la primera vez', async () => {
    const fetchFn = vi.fn(async () => respuesta(buena))
    const r = await crear(fetchFn).enviarMensaje({ mensaje: 'hola', conversacionId: null, idioma: 'en' })
    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('/api/recommendations/chat')
    expect(init.method).toBe('POST')
    expect(init.headers).toMatchObject({ 'Accept-Language': 'en', 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body)).toEqual({ mensaje: 'hola' })
    expect(r.conversacion_id).toBe('c-1')
  })

  it('continúa la conversación enviando su identificador en el cuerpo', async () => {
    const fetchFn = vi.fn(async () => respuesta(buena))
    await crear(fetchFn).enviarMensaje({ mensaje: 'y?', conversacionId: 'c-1' })
    expect(JSON.parse(fetchFn.mock.calls[0][1].body)).toEqual({ mensaje: 'y?', conversacion_id: 'c-1' })
  })

  it('no pone el Authorization: lo pone el fetch autenticado que recibe (authorizedFetch)', async () => {
    const fetchFn = vi.fn(async () => respuesta(buena))
    await crear(fetchFn).enviarMensaje({ mensaje: 'hola', conversacionId: null })
    expect(fetchFn.mock.calls[0][1].headers.Authorization).toBeUndefined()
  })

  it('descarta las recomendaciones mal formadas', async () => {
    const r = await crear(async () => respuesta({ ...buena, recomendaciones: [buena.recomendaciones[0], { nombre: 'sin id' }, null] }))
      .enviarMensaje({ mensaje: 'x', conversacionId: null })
    expect(r.recomendaciones).toHaveLength(1)
  })

  it.each([
    [400, 'VALIDACION'], [401, 'NO_AUTENTICADO'], [403, 'PROHIBIDO'], [404, 'CONVERSACION_NO_ENCONTRADA'],
    [429, 'DEMASIADAS_SOLICITUDES'], [503, 'ASISTENTE_NO_DISPONIBLE'],
  ])('traduce el %i del servicio usando su código', async (status, code) => {
    const e = await falla(crear(async () => respuesta({ error: code, message: 'texto', correlation_id: 'corr-9' }, { status })).enviarMensaje({ mensaje: 'x', conversacionId: null }))
    expect(e).toBeInstanceOf(AssistantError)
    expect(e).toMatchObject({ code, status, message: 'texto', correlationId: 'corr-9' })
  })

  it('lee el Retry-After de un 429', async () => {
    const e = await falla(crear(async () => respuesta({ error: 'DEMASIADAS_SOLICITUDES', message: 'x' }, { status: 429, retryAfter: '120' })).enviarMensaje({ mensaje: 'x', conversacionId: null }))
    expect(e.retryAfter).toBe(120)
  })

  it('el 401 de ForwardAuth (formato de iam, sin `error`) también es NO_AUTENTICADO', async () => {
    const e = await falla(crear(async () => respuesta({ detail: 'Token inválido', code: 'TOKEN_INVALIDO' }, { status: 401 })).enviarMensaje({ mensaje: 'x', conversacionId: null }))
    expect(e).toMatchObject({ code: 'NO_AUTENTICADO', message: 'Token inválido' })
  })

  it.each([502, 504])('un %i de Traefik (sin cuerpo JSON) es ASISTENTE_NO_DISPONIBLE', async (status) => {
    const e = await falla(crear(async () => respuesta(undefined, { status })).enviarMensaje({ mensaje: 'x', conversacionId: null }))
    expect(e.code).toBe('ASISTENTE_NO_DISPONIBLE')
  })

  it('un 404 sin código no se confunde con una conversación vencida', async () => {
    const e = await falla(crear(async () => respuesta(undefined, { status: 404 })).enviarMensaje({ mensaje: 'x', conversacionId: 'c-1' }))
    expect(e.code).toBe('ERROR')
  })

  it('un 200 que no es del asistente (el HTML del frontend) es RESPUESTA_INVALIDA', async () => {
    const e = await falla(crear(async () => respuesta(undefined)).enviarMensaje({ mensaje: 'x', conversacionId: null }))
    expect(e.code).toBe('RESPUESTA_INVALIDA')
    const f = await falla(crear(async () => respuesta({ otra: 'cosa' })).enviarMensaje({ mensaje: 'x', conversacionId: null }))
    expect(f.code).toBe('RESPUESTA_INVALIDA')
  })

  it('sin red lanza SIN_CONEXION', async () => {
    const e = await falla(crear(async () => { throw new TypeError('Failed to fetch') }).enviarMensaje({ mensaje: 'x', conversacionId: null }))
    expect(e.code).toBe('SIN_CONEXION')
  })

  it('aborta a los 50 s y lanza TIEMPO_AGOTADO, no antes', async () => {
    vi.useFakeTimers()
    const fetchFn = vi.fn((_u, init) => new Promise((_r, rechazar) => init.signal.addEventListener('abort', () => rechazar(new DOMException('abortado', 'AbortError')))))
    const pendiente = falla(crear(fetchFn).enviarMensaje({ mensaje: 'x', conversacionId: null }))
    await vi.advanceTimersByTimeAsync(49_000)
    expect(fetchFn.mock.calls[0][1].signal.aborted).toBe(false) // a los 45 s el servicio aún puede responder su 503
    await vi.advanceTimersByTimeAsync(1_500)
    expect((await pendiente).code).toBe('TIEMPO_AGOTADO')
  })

  it('una respuesta a tiempo apaga el temporizador', async () => {
    vi.useFakeTimers()
    await crear(async () => respuesta(buena)).enviarMensaje({ mensaje: 'x', conversacionId: null })
    expect(vi.getTimerCount()).toBe(0)
  })
})
