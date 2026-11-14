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

describe('recargarAlCambiarIdioma', () => {
  // Una pantalla de mentira con la misma forma que las reales: `cargar` enciende `cargando` y, al final, lo apaga
  async function pantalla({ conDatos = true } = {}) {
    const { ref, nextTick } = await import('vue')
    const { recargarAlCambiarIdioma } = await import('../src/lib/refrescoIdioma')
    const locale = ref('es')
    const cargando = ref(false)
    const error = ref('')
    const datos = ref(conDatos ? ['Playa'] : [])
    const llamadas = []
    const esperas = []
    let fallar = false
    async function cargar(...args) {
      cargando.value = true; error.value = ''
      llamadas.push({ idioma: locale.value, args })
      try {
        await new Promise((r) => esperas.push(r))
        if (fallar) throw new Error('falló')
        datos.value = [locale.value === 'en' ? 'Beach' : 'Playa']
      } catch { error.value = 'No se pudo cargar' } finally { cargando.value = false }
    }
    recargarAlCambiarIdioma(locale, { cargar, cargando, error, hayDatos: () => datos.value.length > 0, argumentos: () => ['p2'] })
    const cambiar = async (l) => { locale.value = l; await nextTick() }
    const liberar = async () => { esperas.shift()(); await new Promise((r) => setTimeout(r)) }
    return { locale, cargando, error, datos, llamadas, cambiar, liberar, fallar: (v) => { fallar = v } }
  }

  it('con datos en pantalla no enciende el esqueleto, los conserva hasta que llegan los nuevos y pasa los argumentos', async () => {
    const p = await pantalla()
    await p.cambiar('en')
    expect(p.cargando.value).toBe(false)
    expect(p.datos.value).toEqual(['Playa'])
    expect(refrescandoIdioma.value).toBe(true)
    expect(p.llamadas).toEqual([{ idioma: 'en', args: ['p2'] }])
    await p.liberar()
    expect(p.datos.value).toEqual(['Beach'])
    expect(refrescandoIdioma.value).toBe(false)
  })

  it('si la recarga falla, conserva lo que había y no muestra el error', async () => {
    const p = await pantalla()
    p.fallar(true)
    await p.cambiar('en')
    await p.liberar()
    expect(p.datos.value).toEqual(['Playa'])
    expect(p.error.value).toBe('')
    expect(p.cargando.value).toBe(false)
  })

  it('sin datos que conservar hace la carga normal, con esqueleto', async () => {
    const p = await pantalla({ conDatos: false })
    await p.cambiar('en')
    expect(p.cargando.value).toBe(true)
    await p.liberar()
    expect(p.cargando.value).toBe(false)
  })

  it('ES → EN → ES mientras carga: no lanza peticiones en paralelo y repite una vez con el idioma de ahora', async () => {
    const p = await pantalla()
    await p.cambiar('en')
    await p.cambiar('es')
    await p.cambiar('en')
    expect(p.llamadas).toHaveLength(1) // una sola en vuelo
    await p.liberar() // termina la de EN y se repite con el idioma actual
    expect(p.llamadas).toHaveLength(2)
    expect(p.llamadas[1].idioma).toBe('en')
    await p.liberar()
    expect(p.datos.value).toEqual(['Beach'])
    expect(refrescandoIdioma.value).toBe(false)
  })
})
