import { describe, expect, it, vi } from 'vitest'
import { createWebLocksRenewal } from '../../src/infrastructure/auth/webLocksRenovacion.js'

const pausa = (ms) => new Promise((r) => setTimeout(r, ms))

describe('candado de renovación', () => {
  it('con Web Locks usa un candado con nombre (sirve entre pestañas) y devuelve lo que devuelva la función', async () => {
    const locks = { request: vi.fn(async (_nombre, fn) => fn()) }
    const r = await createWebLocksRenewal({ locks }).run(async () => 'listo')
    expect(r).toBe('listo')
    expect(locks.request).toHaveBeenCalledWith('iam-refresh', expect.any(Function))
  })

  it('si la función falla, el error llega a quien pidió el candado', async () => {
    const locks = { request: (_n, fn) => fn() }
    await expect(createWebLocksRenewal({ locks }).run(async () => { throw new Error('boom') })).rejects.toThrow('boom')
  })

  describe('sin Web Locks (navegador antiguo)', () => {
    it('serializa dentro de la pestaña: una a la vez y en orden', async () => {
      const lock = createWebLocksRenewal({ locks: null })
      const orden = []
      const tarea = (n, ms) => () => lock.run(async () => { orden.push(`inicio ${n}`); await pausa(ms); orden.push(`fin ${n}`) })
      await Promise.all([tarea(1, 15)(), tarea(2, 1)(), tarea(3, 1)()])
      expect(orden).toEqual(['inicio 1', 'fin 1', 'inicio 2', 'fin 2', 'inicio 3', 'fin 3'])
    })

    it('si una falla, la siguiente igual corre', async () => {
      const lock = createWebLocksRenewal({ locks: null })
      const primera = lock.run(async () => { throw new Error('falló') })
      const segunda = lock.run(async () => 'ok')
      await expect(primera).rejects.toThrow('falló')
      await expect(segunda).resolves.toBe('ok')
    })
  })
})
