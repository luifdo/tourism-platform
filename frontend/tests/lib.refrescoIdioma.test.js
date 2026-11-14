import { describe, expect, it } from 'vitest'
import { conRefresco, refrescandoIdioma } from '../src/lib/refrescoIdioma'

describe('refrescoIdioma', () => {
  it('está encendido mientras haya algo pendiente y se apaga al terminar todo', async () => {
    let liberarA, liberarB
    const a = conRefresco(() => new Promise((r) => { liberarA = r }))
    const b = conRefresco(() => new Promise((r) => { liberarB = r }))
    expect(refrescandoIdioma.value).toBe(true)
    liberarA(); await a
    expect(refrescandoIdioma.value).toBe(true) // todavía falta b
    liberarB(); await b
    expect(refrescandoIdioma.value).toBe(false)
  })

  it('devuelve lo que devuelve la tarea', async () => {
    expect(await conRefresco(async () => 42)).toBe(42)
  })

  it('si la tarea falla, el contador baja igual y el error le llega a quien llamó', async () => {
    await expect(conRefresco(async () => { throw new Error('falló') })).rejects.toThrow('falló')
    expect(refrescandoIdioma.value).toBe(false)
  })
})
