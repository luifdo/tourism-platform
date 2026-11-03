import { beforeEach, describe, expect, it } from 'vitest'
import { createMockAssistantGateway } from '../../src/infrastructure/assistant/mockAssistantGateway.js'
import { responderDemo } from '../../src/infrastructure/assistant/demoRespuestas.js'
import { assertAssistantGateway } from '../../src/application/assistant/ports.js'
import { experiences } from '../../src/data/mock.js'

const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }
let ahora, turista, gw
beforeEach(() => {
  ahora = new Date('2026-11-03T15:00:00Z')
  turista = 'turista-1'
  let n = 0
  gw = createMockAssistantGateway({ clock: { now: () => ahora }, turistaId: () => turista, esperaMs: 0, sleep: async () => {}, newId: () => `conv-${++n}` })
})
const enviar = (mensaje, conversacionId = null, idioma = 'es') => gw.enviarMensaje({ mensaje, conversacionId, idioma })

describe('asistente simulado como servidor del contrato', () => {
  it('implementa el puerto AssistantGateway', () => {
    expect(assertAssistantGateway(gw)).toBeTruthy()
  })

  it('responde con la forma del contrato y crea la conversación', async () => {
    const r = await enviar('quiero ir a la playa')
    expect(r.conversacion_id).toBe('conv-1')
    expect(typeof r.respuesta).toBe('string')
    expect(r.recomendaciones[0]).toMatchObject({ servicio_id: 'bahia-concha' })
    expect(Object.keys(r.recomendaciones[0]).sort()).toEqual(['justificacion_explicabilidad', 'nombre', 'servicio_id'])
  })

  it('solo recomienda servicios que existen en el catálogo simulado', async () => {
    const ids = new Set(experiences.map((e) => e.id))
    for (const m of ['playa y snorkel', 'cascada y caminata', 'cacao y cultura', 'llueve mucho'])
      for (const r of (await enviar(m)).recomendaciones) expect(ids.has(r.servicio_id)).toBe(true)
  })

  it('con lluvia sugiere la experiencia bajo techo', async () => {
    expect((await enviar('¿Qué puedo hacer en Santa Marta con lluvia?')).recomendaciones.map((r) => r.servicio_id)).toEqual(['ruta-cacao'])
  })

  it('responde en el idioma pedido', async () => {
    const es = await enviar('playa', null, 'es')
    const en = await enviar('beach', null, 'en')
    expect(es.recomendaciones[0].nombre).toBe('Santuario Coralino Bahía Concha')
    expect(en.recomendaciones[0].nombre).toBe('Bahía Concha Coral Sanctuary')
  })

  it('un saludo o algo que no entiende no recomienda nada', async () => {
    expect((await enviar('hola')).recomendaciones).toEqual([])
    expect((await enviar('asdf qwer')).recomendaciones).toEqual([])
  })

  it('continúa una conversación existente con el mismo identificador', async () => {
    const a = await enviar('hola')
    const b = await enviar('playa', a.conversacion_id)
    expect(b.conversacion_id).toBe(a.conversacion_id)
  })

  it('exige identidad', async () => {
    turista = null
    expect(await falla(enviar('hola'))).toMatchObject({ code: 'NO_AUTENTICADO', status: 401 })
  })

  it('valida el mensaje como el servidor', async () => {
    expect(await falla(enviar('   '))).toMatchObject({ code: 'VALIDACION', status: 400 })
    expect(await falla(enviar('a'.repeat(1001)))).toMatchObject({ code: 'VALIDACION', status: 400 })
  })

  it('una conversación desconocida, de otro turista o de más de 24 h da el mismo 404', async () => {
    expect(await falla(enviar('hola', 'no-existe'))).toMatchObject({ code: 'CONVERSACION_NO_ENCONTRADA', status: 404 })
    const { conversacion_id: id } = await enviar('hola')
    turista = 'turista-2'
    expect((await falla(enviar('hola', id))).code).toBe('CONVERSACION_NO_ENCONTRADA')
    turista = 'turista-1'
    ahora = new Date(ahora.getTime() + 24 * 3600 * 1000 + 1000)
    expect((await falla(enviar('hola', id))).code).toBe('CONVERSACION_NO_ENCONTRADA')
  })

  it('limita a 10 mensajes cada 5 minutos por turista y dice cuánto esperar', async () => {
    for (let i = 0; i < 10; i++) await enviar('hola')
    const e = await falla(enviar('hola'))
    expect(e).toMatchObject({ code: 'DEMASIADAS_SOLICITUDES', status: 429, retryAfter: 300 })
    turista = 'turista-2'
    await enviar('hola') // el límite es por turista
    turista = 'turista-1'
    ahora = new Date(ahora.getTime() + 5 * 60 * 1000 + 1)
    await enviar('hola') // pasada la ventana vuelve a responder
  })

  it('un mensaje rechazado no gasta cupo del límite', async () => {
    for (let i = 0; i < 20; i++) await falla(enviar(''))
    await enviar('hola')
  })
})

describe('conocimiento del asistente simulado', () => {
  it('reconoce palabras con acentos y mayúsculas', () => {
    expect(responderDemo('SÍ, ¡Cascadas y río!', 'es').recomendaciones[0].servicio_id).toBe('quebrada-valencia')
  })
  it('recomienda como máximo dos servicios', () => {
    expect(responderDemo('playa cascada cacao', 'es').recomendaciones.length).toBeLessThanOrEqual(2)
  })
})
