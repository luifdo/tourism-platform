import { beforeEach, describe, expect, it } from 'vitest'
import { createMockCatalogGateway } from '../../src/infrastructure/catalog/mockCatalogGateway.js'
import { DEMO_SERVICIOS } from '../../src/infrastructure/catalog/demoCatalogo.js'
import { demoServices } from '../../src/infrastructure/booking/demoServices.js'
import { assertCatalogGateway } from '../../src/application/catalog/ports.js'
import { CATEGORIAS } from '../../src/domain/catalog/rules.js'

const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }
let gw
beforeEach(() => { gw = createMockCatalogGateway({ esperaMs: 0, sleep: async () => {} }) })

describe('catálogo simulado como servidor del contrato', () => {
  it('implementa el puerto CatalogGateway', () => {
    expect(assertCatalogGateway(gw)).toBeTruthy()
  })

  it('todos los servicios de demostración existen también en el booking simulado (si no, no se podrían reservar)', () => {
    for (const s of DEMO_SERVICIOS) expect(demoServices[s.id], s.id).toBeTruthy()
  })

  it('usa categorías del contrato', () => {
    for (const s of DEMO_SERVICIOS) expect(CATEGORIAS).toContain(s.categoria)
  })

  it('lista los servicios con la forma del modelo de la aplicación', async () => {
    const r = await gw.buscarServicios({ pagina: 1, tamano: 12, idioma: 'es' })
    expect(r.total).toBe(DEMO_SERVICIOS.length)
    expect(r.items[0]).toMatchObject({ id: 'bahia-concha', nombre: 'Santuario Coralino Bahía Concha', categoria: 'PLAYA', tarifaBase: 130000, unidadEtiqueta: 'por persona' })
  })

  it('responde en el idioma pedido', async () => {
    expect((await gw.buscarServicios({ pagina: 1, tamano: 12, idioma: 'en' })).items[0].nombre).toBe('Bahía Concha Coral Sanctuary')
    expect((await gw.obtenerServicio('ruta-cacao', 'en')).reglaCancelacion).toMatch(/cancel/i)
  })

  it('filtra por categoría y por texto, sin importar acentos ni mayúsculas', async () => {
    expect((await gw.buscarServicios({ categorias: ['CULTURA'], pagina: 1, tamano: 12 })).items.map((s) => s.id)).toEqual(['ruta-cacao'])
    expect((await gw.buscarServicios({ texto: 'CASCADAS', pagina: 1, tamano: 12 })).items.map((s) => s.id)).toEqual(['quebrada-valencia'])
    expect((await gw.buscarServicios({ texto: 'bahia', pagina: 1, tamano: 12 })).total).toBe(1)
    expect((await gw.buscarServicios({ texto: 'inexistente', pagina: 1, tamano: 12 })).items).toEqual([])
  })

  it('pagina', async () => {
    const p1 = await gw.buscarServicios({ pagina: 1, tamano: 2 })
    const p2 = await gw.buscarServicios({ pagina: 2, tamano: 2 })
    expect([p1.items.length, p2.items.length, p1.total]).toEqual([2, 1, 3])
  })

  it('la ficha trae detalle, prestador y alertas; un id desconocido es NO_ENCONTRADO', async () => {
    const s = await gw.obtenerServicio('quebrada-valencia', 'es')
    expect(s).toMatchObject({ capacidadDiaria: 15, prestador: { razonSocial: 'Guías Comunitarios de Guachaca' } })
    expect(s.alertas[0]).toMatchObject({ nivel: 'INFORMATIVA', mensaje: 'El sendero cierra los lunes.' })
    expect(await falla(gw.obtenerServicio('nada', 'es'))).toMatchObject({ code: 'NO_ENCONTRADO', status: 404 })
  })

  it('los nombres omiten los ids que no existen', async () => {
    expect(await gw.nombresServicios(['ruta-cacao', 'nada'], 'es')).toEqual([{ id: 'ruta-cacao', nombre: 'Ruta del Cacao y Sabiduría Textil', activo: true }])
  })

  it('"cómo llegar" a un servicio que no existe es 404', async () => {
    await gw.registrarIntencionVisita('ruta-cacao')
    expect((await falla(gw.registrarIntencionVisita('nada'))).code).toBe('NO_ENCONTRADO')
  })

  it('el mapa devuelve solo lo que cae en la vista', async () => {
    const todo = await gw.mapaServicios({ bbox: [-75, 10, -73, 12], zoom: 10, idioma: 'es' })
    expect(todo).toHaveLength(3)
    expect(todo[0]).toMatchObject({ tipo: 'servicio', lat: expect.any(Number), lon: expect.any(Number) })
    const soloTaganga = await gw.mapaServicios({ bbox: [-74.2, 11.3, -74.0, 11.4], zoom: 12 })
    expect(soloTaganga.map((p) => p.id)).toEqual(['bahia-concha'])
  })
})
