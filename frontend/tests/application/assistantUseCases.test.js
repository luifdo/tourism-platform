import { describe, expect, it, vi } from 'vitest'
import { createAssistantUseCases } from '../../src/application/assistant/useCases.js'
import { AssistantError } from '../../src/domain/assistant/errors.js'

const rec = { servicio_id: 's-1', nombre: 'Bahía Concha', justificacion_explicabilidad: 'Porque sí' }
const respuesta = (id = 'c-1') => ({ conversacion_id: id, respuesta: 'Hola', recomendaciones: [rec] })
const crear = (enviarMensaje, autenticado = true) =>
  createAssistantUseCases({ gateway: { enviarMensaje }, session: { isAuthenticated: () => autenticado } })
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }

describe('casos de uso del asistente', () => {
  it('exige que el adaptador implemente el puerto', () => {
    expect(() => createAssistantUseCases({ gateway: {}, session: {} })).toThrow(/AssistantGateway/)
  })

  it('el primer mensaje va sin conversación y los siguientes la continúan', async () => {
    const gw = vi.fn(async () => respuesta('c-1'))
    const uc = crear(gw)
    await uc.enviar('hola')
    await uc.enviar('y con lluvia?')
    expect(gw.mock.calls[0][0]).toEqual({ mensaje: 'hola', conversacionId: null, idioma: 'es' })
    expect(gw.mock.calls[1][0].conversacionId).toBe('c-1')
    expect(uc.conversacionActual()).toBe('c-1')
  })

  it('devuelve las recomendaciones con los nombres de la aplicación', async () => {
    const r = await crear(async () => respuesta()).enviar('hola', { idioma: 'en' })
    expect(r.recomendaciones).toEqual([{ servicioId: 's-1', nombre: 'Bahía Concha', justificacion: 'Porque sí' }])
    expect(r.conversacionReiniciada).toBe(false)
  })

  it('no llama al servicio con un mensaje vacío, largo o sin sesión', async () => {
    const gw = vi.fn(async () => respuesta())
    const uc = crear(gw)
    expect((await falla(uc.enviar('   '))).code).toBe('MENSAJE_VACIO')
    expect((await falla(uc.enviar('a'.repeat(1001)))).code).toBe('MENSAJE_LARGO')
    expect((await falla(crear(gw, false).enviar('hola'))).code).toBe('NO_AUTENTICADO')
    expect(gw).not.toHaveBeenCalled()
  })

  it('si la conversación ya no existe, reenvía el mensaje sin ella y avisa', async () => {
    const gw = vi.fn()
      .mockResolvedValueOnce(respuesta('c-1'))
      .mockRejectedValueOnce(new AssistantError('CONVERSACION_NO_ENCONTRADA', 'expiró', { status: 404 }))
      .mockResolvedValueOnce(respuesta('c-2'))
    const uc = crear(gw)
    await uc.enviar('uno')
    const r = await uc.enviar('dos')
    expect(r.conversacionReiniciada).toBe(true)
    expect(gw.mock.calls[2][0].conversacionId).toBeNull()
    expect(uc.conversacionActual()).toBe('c-2')
  })

  it('un 404 en el primer mensaje no se reintenta (no había conversación que borrar)', async () => {
    const gw = vi.fn().mockRejectedValue(new AssistantError('CONVERSACION_NO_ENCONTRADA', 'x', { status: 404 }))
    expect((await falla(crear(gw).enviar('hola'))).code).toBe('CONVERSACION_NO_ENCONTRADA')
    expect(gw).toHaveBeenCalledTimes(1)
  })

  it('los demás errores del servicio se propagan tal cual y no pierden la conversación', async () => {
    const gw = vi.fn()
      .mockResolvedValueOnce(respuesta('c-1'))
      .mockRejectedValueOnce(new AssistantError('ASISTENTE_NO_DISPONIBLE', 'sin IA', { status: 503 }))
    const uc = crear(gw)
    await uc.enviar('uno')
    expect((await falla(uc.enviar('dos'))).code).toBe('ASISTENTE_NO_DISPONIBLE')
    expect(uc.conversacionActual()).toBe('c-1')
  })

  it('una respuesta que llega después de empezar de nuevo no revive la conversación anterior', async () => {
    let resolver
    const gw = vi.fn(() => new Promise((r) => { resolver = r }))
    const uc = crear(gw)
    const pendiente = uc.enviar('hola')
    uc.nuevaConversacion()
    resolver(respuesta('vieja'))
    await pendiente
    expect(uc.conversacionActual()).toBeNull()
  })
})
