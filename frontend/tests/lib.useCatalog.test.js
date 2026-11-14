import { beforeEach, describe, expect, it, vi } from 'vitest'

const explorar = vi.fn()
vi.mock('../src/composition', () => ({ catalogUseCases: { explorar } }))
const { useCatalog } = await import('../src/lib/useCatalog')

const pagina = (nombre) => ({ items: [{ id: 'a', nombre }], total: 1, desdeCache: false, actualizadoEn: null })

describe('useCatalog: recarga al cambiar de idioma', () => {
  beforeEach(() => explorar.mockReset())

  it('carga normal: muestra el esqueleto (cargando) hasta que llegan los resultados', async () => {
    const { estado, cargar } = useCatalog()
    explorar.mockResolvedValueOnce(pagina('Beach'))
    const p = cargar({}, 'en')
    expect(estado.cargando).toBe(true)
    await p
    expect(estado.cargando).toBe(false)
    expect(estado.items[0].nombre).toBe('Beach')
  })

  it('silenciosa con resultados en pantalla: no muestra el esqueleto y conserva las tarjetas hasta que llegan las nuevas', async () => {
    const { estado, cargar } = useCatalog()
    explorar.mockResolvedValueOnce(pagina('Playa'))
    await cargar({}, 'es')
    let llega
    explorar.mockReturnValueOnce(new Promise((r) => { llega = r }))
    const p = cargar({}, 'en', { silencioso: true })
    expect(estado.cargando).toBe(false)
    expect(estado.actualizando).toBe(true)
    expect(estado.items[0].nombre).toBe('Playa') // todavía en español
    llega(pagina('Beach')); await p
    expect(estado.actualizando).toBe(false)
    expect(estado.items[0].nombre).toBe('Beach')
  })

  it('silenciosa que falla: conserva lo que había y no muestra un error', async () => {
    const { estado, cargar } = useCatalog()
    explorar.mockResolvedValueOnce(pagina('Playa'))
    await cargar({}, 'es')
    explorar.mockRejectedValueOnce(Object.assign(new Error('x'), { code: 'RED' }))
    await cargar({}, 'en', { silencioso: true })
    expect(estado.items[0].nombre).toBe('Playa')
    expect(estado.error).toBeNull()
    expect(estado.actualizando).toBe(false)
  })

  it('silenciosa sin resultados previos: se comporta como una carga normal', async () => {
    const { estado, cargar } = useCatalog()
    explorar.mockResolvedValueOnce({ items: [], total: 0, desdeCache: false, actualizadoEn: null })
    await cargar({}, 'es') // deja el estado compartido vacío
    let llega
    explorar.mockReturnValueOnce(new Promise((r) => { llega = r }))
    const p = cargar({}, 'en', { silencioso: true })
    expect(estado.cargando).toBe(true)
    llega(pagina('Beach')); await p
    expect(estado.cargando).toBe(false)
  })

  it('una carga nueva descarta la respuesta de la silenciosa anterior', async () => {
    const { estado, cargar } = useCatalog()
    explorar.mockResolvedValueOnce(pagina('Playa'))
    await cargar({}, 'es')
    let llegaVieja
    explorar.mockReturnValueOnce(new Promise((r) => { llegaVieja = r }))
    const vieja = cargar({}, 'en', { silencioso: true })
    explorar.mockResolvedValueOnce(pagina('Beach (filtrado)'))
    await cargar({ texto: 'x' }, 'en')
    llegaVieja(pagina('Beach')); await vieja
    expect(estado.items[0].nombre).toBe('Beach (filtrado)')
  })
})
