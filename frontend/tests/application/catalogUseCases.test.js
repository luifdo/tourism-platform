import { describe, expect, it, vi } from 'vitest'
import { createCatalogUseCases } from '../../src/application/catalog/useCases.js'
import { CatalogError } from '../../src/domain/catalog/errors.js'

const servicio = (id) => ({ id, nombre: `S ${id}` })
const gw = (extra = {}) => ({
  buscarServicios: vi.fn(async ({ pagina }) => ({ items: [servicio('a')], pagina, tamano: 12, total: 1 })),
  obtenerServicio: vi.fn(async (id) => servicio(id)),
  nombresServicios: vi.fn(async (ids) => ids.map((id) => ({ id, nombre: `N ${id}`, activo: true }))),
  registrarIntencionVisita: vi.fn(async () => {}),
  mapaServicios: vi.fn(async () => []),
  serviciosPrestador: vi.fn(async () => ({ items: [], pagina: 1, tamano: 100, total: 0 })),
  zonas: vi.fn(async () => [{ codigo: 'taganga', nombre: 'Taganga' }]),
  mapaZonas: vi.fn(async () => []),
  mapaAlertas: vi.fn(async () => []),
  ...extra,
})
const memoria = (inicial = null) => { let v = inicial; return { read: vi.fn(async () => v), write: vi.fn(async (x) => { v = x }) } }
const T = new Date('2026-11-12T15:00:00Z')
const crear = (g, cache = memoria()) => createCatalogUseCases({ gateway: g, cache, clock: { now: () => T } })
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }

describe('casos de uso del catálogo', () => {
  it('exige que el adaptador implemente el puerto', () => {
    expect(() => createCatalogUseCases({ gateway: {} })).toThrow(/CatalogGateway/)
  })

  describe('explorar', () => {
    it('normaliza la búsqueda antes de pedirla', async () => {
      const g = gw()
      await crear(g).explorar({ texto: '  mar ', categorias: ['PLAYA', 'X'], pagina: 0 }, { idioma: 'en' })
      expect(g.buscarServicios).toHaveBeenCalledWith({ texto: 'mar', categorias: ['PLAYA'], pagina: 1, tamano: 12, idioma: 'en', zona: null, precioMin: null, precioMax: null, fecha: null, personas: null, orden: null })
    })

    it('guarda la portada (página 1 sin filtros) para verla sin conexión', async () => {
      const cache = memoria()
      const r = await crear(gw(), cache).explorar({})
      expect(cache.write).toHaveBeenCalledWith({ items: [servicio('a')], total: 1, at: T.getTime() })
      expect(r).toMatchObject({ desdeCache: false, actualizadoEn: T.getTime() })
    })

    it('no guarda en la caché las búsquedas con filtros ni las páginas siguientes', async () => {
      const cache = memoria()
      const uc = crear(gw(), cache)
      await uc.explorar({ texto: 'mar' })
      await uc.explorar({ categorias: ['PLAYA'] })
      await uc.explorar({ pagina: 2 })
      expect(cache.write).not.toHaveBeenCalled()
    })

    it('sin conexión devuelve la portada guardada, con su fecha', async () => {
      const cache = memoria({ items: [servicio('z')], total: 7, at: 123 })
      const uc = crear(gw({ buscarServicios: vi.fn().mockRejectedValue(new CatalogError('SIN_CONEXION', 'x')) }), cache)
      expect(await uc.explorar({})).toEqual({ items: [servicio('z')], pagina: 1, tamano: 1, total: 7, desdeCache: true, actualizadoEn: 123 })
    })

    it('sin conexión y sin copia, o con filtros, el error se propaga', async () => {
      const g = gw({ buscarServicios: vi.fn().mockRejectedValue(new CatalogError('SIN_CONEXION', 'x')) })
      expect((await falla(crear(g, memoria()).explorar({}))).code).toBe('SIN_CONEXION')
      expect((await falla(crear(g, memoria({ items: [servicio('z')], total: 1, at: 1 })).explorar({ texto: 'mar' }))).code).toBe('SIN_CONEXION')
    })

    it('con el catálogo caído (5xx, como el 502 de Traefik) también devuelve la copia', async () => {
      for (const status of [500, 502, 503, 504]) {
        const g = gw({ buscarServicios: vi.fn().mockRejectedValue(new CatalogError('ERROR', 'boom', { status })) })
        const r = await crear(g, memoria({ items: [servicio('z')], total: 1, at: 9 })).explorar({})
        expect(r).toMatchObject({ desdeCache: true, actualizadoEn: 9 })
      }
    })

    it('los errores del cliente no se esconden detrás de la copia (un 400 o una respuesta inválida son bugs, no caídas)', async () => {
      const cache = memoria({ items: [servicio('z')], total: 1, at: 1 })
      const g400 = gw({ buscarServicios: vi.fn().mockRejectedValue(new CatalogError('VALIDACION', 'mal', { status: 400 })) })
      const gInvalida = gw({ buscarServicios: vi.fn().mockRejectedValue(new CatalogError('RESPUESTA_INVALIDA', 'x', { status: 200 })) })
      expect((await falla(crear(g400, cache).explorar({}))).code).toBe('VALIDACION')
      expect((await falla(crear(gInvalida, cache).explorar({}))).code).toBe('RESPUESTA_INVALIDA')
    })

    it('un fallo al guardar la copia no rompe la búsqueda', async () => {
      const cache = { read: vi.fn(), write: vi.fn().mockRejectedValue(new Error('IndexedDB')) }
      expect((await crear(gw(), cache).explorar({})).items).toHaveLength(1)
    })
  })

  describe('ficha', () => {
    it('pide el servicio en el idioma pedido', async () => {
      const g = gw()
      expect(await crear(g).ficha('abc', { idioma: 'en' })).toEqual(servicio('abc'))
      expect(g.obtenerServicio).toHaveBeenCalledWith('abc', 'en')
    })
    it('sin id es NO_ENCONTRADO y no llama al servicio', async () => {
      const g = gw()
      expect((await falla(crear(g).ficha(''))).code).toBe('NO_ENCONTRADO')
      expect(g.obtenerServicio).not.toHaveBeenCalled()
    })
  })

  describe('nombres (reservas y reseñas solo traen servicio_id)', () => {
    it('devuelve los nombres por id y quita los repetidos y los vacíos', async () => {
      const g = gw()
      const r = await crear(g).nombres(['a', 'b', 'a', '', null, undefined])
      expect(g.nombresServicios).toHaveBeenCalledTimes(1)
      expect(g.nombresServicios.mock.calls[0][0]).toEqual(['a', 'b'])
      expect(r).toEqual({ porId: { a: { nombre: 'N a', activo: true }, b: { nombre: 'N b', activo: true } }, incompleto: false })
    })

    it('un id que el servicio no devuelve queda fuera: ya no existe', async () => {
      const g = gw({ nombresServicios: vi.fn(async () => [{ id: 'a', nombre: 'A', activo: false }]) })
      const r = await crear(g).nombres(['a', 'borrado'])
      expect(r.porId).toEqual({ a: { nombre: 'A', activo: false } })
      expect(r.incompleto).toBe(false)
    })

    it('parte las consultas en tandas de 100 ids (límite del contrato)', async () => {
      const g = gw()
      const ids = Array.from({ length: 230 }, (_, i) => `id-${i}`)
      const r = await crear(g).nombres(ids)
      expect(g.nombresServicios.mock.calls.map((c) => c[0].length).sort((a, b) => b - a)).toEqual([100, 100, 30])
      expect(Object.keys(r.porId)).toHaveLength(230)
    })

    it('sin ids no llama al servicio', async () => {
      const g = gw()
      expect(await crear(g).nombres([])).toEqual({ porId: {}, incompleto: false })
      expect(g.nombresServicios).not.toHaveBeenCalled()
    })

    it('si una llamada falla, avisa que está incompleto en vez de decir que no existen', async () => {
      const g = gw({ nombresServicios: vi.fn().mockRejectedValue(new CatalogError('SIN_CONEXION', 'x')) })
      expect(await crear(g).nombres(['a'])).toEqual({ porId: {}, incompleto: true })
    })

    it('si falla una sola tanda, conserva los nombres de las demás', async () => {
      const g = gw({ nombresServicios: vi.fn(async (ids) => { if (ids[0] === 'id-0') throw new CatalogError('ERROR', 'x'); return ids.map((id) => ({ id, nombre: id, activo: true })) }) })
      const r = await crear(g).nombres(Array.from({ length: 150 }, (_, i) => `id-${i}`))
      expect(r.incompleto).toBe(true)
      expect(Object.keys(r.porId)).toHaveLength(50)
    })
  })

  it('comoLlegar nunca falla hacia el turista: devuelve si se pudo contar', async () => {
    expect(await crear(gw()).comoLlegar('a')).toBe(true)
    expect(await crear(gw({ registrarIntencionVisita: vi.fn().mockRejectedValue(new CatalogError('ERROR', 'x')) })).comoLlegar('a')).toBe(false)
  })

  it('puntosDelMapa pasa la vista y descarta categorías inválidas', async () => {
    const g = gw()
    await crear(g).puntosDelMapa({ bbox: [-75, 10, -73, 12], zoom: 10, categorias: ['PLAYA', 'X'] }, { idioma: 'en' })
    expect(g.mapaServicios).toHaveBeenCalledWith({ bbox: [-75, 10, -73, 12], zoom: 10, categorias: ['PLAYA'], idioma: 'en' })
  })
  describe('misServicios (UC18)', () => {
    it('lee todas las páginas de a 100 hasta completar el total', async () => {
      const g = gw({ serviciosPrestador: vi.fn(async ({ pagina }) => ({ items: Array.from({ length: pagina === 3 ? 20 : 100 }, (_, i) => ({ id: `${pagina}-${i}` })), pagina, tamano: 100, total: 220 })) })
      const todos = await crear(g).misServicios({ idioma: 'en' })
      expect(todos).toHaveLength(220)
      expect(g.serviciosPrestador).toHaveBeenCalledTimes(3)
      expect(g.serviciosPrestador).toHaveBeenCalledWith({ pagina: 1, tamano: 100 }, 'en')
    })
    it('sin servicios devuelve la lista vacía y no insiste', async () => {
      const g = gw()
      expect(await crear(g).misServicios()).toEqual([])
      expect(g.serviciosPrestador).toHaveBeenCalledTimes(1)
    })
    it('el error del servicio (403, 401) se propaga', async () => {
      const g = gw({ serviciosPrestador: vi.fn().mockRejectedValue(new CatalogError('ERROR', 'no', { status: 403 })) })
      expect((await falla(crear(g).misServicios())).status).toBe(403)
    })
  })
})

describe('filtros del explorador', () => {
  it('pasa zona, precios, fecha, personas y orden ya normalizados', async () => {
    const g = gw(); const uc = crear(g)
    await uc.explorar({ texto: ' kayak ', zona: ' taganga ', precioMin: '200000', precioMax: '50000', fecha: '2026-12-01', personas: '3', orden: 'precio' }, { idioma: 'es' })
    expect(g.buscarServicios).toHaveBeenCalledWith(expect.objectContaining({ texto: 'kayak', zona: 'taganga', precioMin: 50000, precioMax: 200000, fecha: '2026-12-01', personas: 3, orden: 'precio' }))
  })
  it('descarta lo inválido en vez de mandarlo (fecha mal escrita, orden desconocido, personas 0, precio negativo)', async () => {
    const g = gw(); const uc = crear(g)
    await uc.explorar({ fecha: '1/12/2026', orden: 'azar', personas: 0, precioMin: -5, precioMax: '' }, { idioma: 'es' })
    expect(g.buscarServicios).toHaveBeenCalledWith(expect.objectContaining({ fecha: null, orden: null, personas: null, precioMin: null, precioMax: null }))
  })
  it('personas sin fecha no se manda (el servicio respondería 400)', async () => {
    const g = gw(); await crear(g).explorar({ personas: 4 }, { idioma: 'es' })
    expect(g.buscarServicios).toHaveBeenCalledWith(expect.objectContaining({ personas: null, fecha: null }))
  })
  it('una búsqueda con filtros no es la portada: no se guarda para verla sin conexión', async () => {
    const cache = memoria(); const uc = crear(gw(), cache)
    await uc.explorar({ zona: 'minca' }, { idioma: 'es' })
    expect(cache.write).not.toHaveBeenCalled()
    await uc.explorar({}, { idioma: 'es' })
    expect(cache.write).toHaveBeenCalledTimes(1)
  })
  it('las zonas del filtro vienen del catálogo', async () => {
    expect(await crear(gw()).zonas('en')).toEqual([{ codigo: 'taganga', nombre: 'Taganga' }])
  })
})
