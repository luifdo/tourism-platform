import { describe, expect, it, vi } from 'vitest'
import { createHttpCatalogGateway } from '../../src/infrastructure/catalog/httpCatalogGateway.js'
import { assertCatalogGateway } from '../../src/application/catalog/ports.js'
import { CatalogError } from '../../src/domain/catalog/errors.js'

const respuesta = (cuerpo, { status = 200 } = {}) => ({
  ok: status < 400, status, statusText: 'x',
  json: async () => { if (cuerpo === undefined) throw new SyntaxError('no es JSON'); return cuerpo },
})
const crear = (fetchFn) => createHttpCatalogGateway({ baseUrl: '/api/catalog', fetchFn })
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }

const resumen = {
  id: '11111111-1111-4111-8111-111111111111', nombre: 'Bahía Concha', tipo: 'DEPORTE_ACUATICO', tipo_etiqueta: 'Deporte acuático',
  categoria: 'PLAYA', categoria_etiqueta: 'Playas', zona: { codigo: 'taganga', nombre: 'Taganga' },
  ubicacion: { lat: 11.32, lon: -74.09 }, tarifa_base: 130000, unidad_tarifa: 'POR_PERSONA', unidad_tarifa_etiqueta: 'por persona',
  calificacion_promedio: 4.5, total_resenas: 8,
}
const detalle = {
  ...resumen, descripcion: 'Texto', capacidad_aforo_diario: 20, imagenes_urls: ['https://s3.ejemplo/img.jpg', 7],
  regla_base_cancelacion: 'Hasta las 23:59', prestador: { id: 'p1', razon_social: 'Pescadores', telefono: null, politica_cancelacion: 'Política' },
  alertas: [{ id: 'a1', nivel: 'PREVENTIVA', nivel_etiqueta: 'Preventiva', mensaje: 'Oleaje', fecha_expiracion: '2026-12-01T00:00:00Z' }],
  etiquetas: { SIN_SENAL: 'Sin señal', EFECTIVO: 'Efectivo' },
  aviso_pagos: { importante: true, recomendacion_dinero: 'EFECTIVO', mensaje: 'Lleva efectivo' }, atributos: {},
}

describe('adaptador HTTP del catálogo', () => {
  it('implementa el puerto CatalogGateway', () => {
    expect(assertCatalogGateway(crear(vi.fn()))).toBeTruthy()
  })

  describe('buscarServicios', () => {
    it('pide /buscar con los filtros del contrato y el idioma', async () => {
      const fetchFn = vi.fn(async () => respuesta({ items: [], pagina: 1, tamano: 12, total: 0 }))
      await crear(fetchFn).buscarServicios({ texto: 'mar azul', categorias: ['PLAYA', 'CULTURA'], pagina: 2, tamano: 12, idioma: 'en' })
      const [url, init] = fetchFn.mock.calls[0]
      const u = new URL(url, 'http://x')
      expect(u.pathname).toBe('/api/catalog/buscar')
      expect(Object.fromEntries(u.searchParams)).toEqual({ texto: 'mar azul', categoria: 'PLAYA,CULTURA', pagina: '2', tamano: '12' })
      expect(init.method).toBe('GET')
      expect(init.headers['Accept-Language']).toBe('en')
      expect(init.headers.Authorization).toBeUndefined() // ruta pública
    })

    it('omite los filtros vacíos', async () => {
      const fetchFn = vi.fn(async () => respuesta({ items: [], total: 0 }))
      await crear(fetchFn).buscarServicios({ texto: '', categorias: [], pagina: 1, tamano: 12 })
      expect(fetchFn.mock.calls[0][0]).toBe('/api/catalog/buscar?pagina=1&tamano=12')
    })

    it('convierte cada ServicioResumen al modelo de la aplicación', async () => {
      const r = await crear(async () => respuesta({ items: [resumen], pagina: 1, tamano: 12, total: 1 })).buscarServicios({ pagina: 1, tamano: 12 })
      expect(r.total).toBe(1)
      expect(r.items[0]).toEqual({
        id: resumen.id, nombre: 'Bahía Concha', tipo: 'DEPORTE_ACUATICO', tipoEtiqueta: 'Deporte acuático', categoria: 'PLAYA', categoriaEtiqueta: 'Playas',
        zona: { codigo: 'taganga', nombre: 'Taganga' }, ubicacion: { lat: 11.32, lon: -74.09 }, tarifaBase: 130000,
        unidadTarifa: 'POR_PERSONA', unidadEtiqueta: 'por persona', calificacion: 4.5, totalResenas: 8,
      })
    })

    it('tolera una zona nula y una calificación nula (servicio sin reseñas)', async () => {
      const r = await crear(async () => respuesta({ items: [{ ...resumen, zona: null, calificacion_promedio: null, total_resenas: undefined }], total: 1 })).buscarServicios({ pagina: 1 })
      expect(r.items[0]).toMatchObject({ zona: null, calificacion: null, totalResenas: 0 })
    })

    it('una respuesta sin `items` (el HTML del frontend, otra cosa) es RESPUESTA_INVALIDA', async () => {
      expect((await falla(crear(async () => respuesta({ otra: 1 })).buscarServicios({ pagina: 1 }))).code).toBe('RESPUESTA_INVALIDA')
      expect((await falla(crear(async () => respuesta(undefined)).buscarServicios({ pagina: 1 }))).code).toBe('RESPUESTA_INVALIDA')
    })
  })

  describe('obtenerServicio', () => {
    it('pide /servicios/{id} y convierte el detalle', async () => {
      const fetchFn = vi.fn(async () => respuesta(detalle))
      const s = await crear(fetchFn).obtenerServicio('11111111-1111-4111-8111-111111111111', 'es')
      expect(fetchFn.mock.calls[0][0]).toBe('/api/catalog/servicios/11111111-1111-4111-8111-111111111111')
      expect(s).toMatchObject({
        descripcion: 'Texto', capacidadDiaria: 20, reglaCancelacion: 'Hasta las 23:59',
        imagenes: ['https://s3.ejemplo/img.jpg'], // descarta lo que no es una URL de texto
        prestador: { id: 'p1', razonSocial: 'Pescadores', telefono: null, politicaCancelacion: 'Política' },
        alertas: [{ id: 'a1', nivel: 'PREVENTIVA', nivelEtiqueta: 'Preventiva', mensaje: 'Oleaje', fechaExpiracion: '2026-12-01T00:00:00Z' }],
        etiquetas: ['Sin señal', 'Efectivo'],
        avisoPagos: { importante: true, recomendacionDinero: 'EFECTIVO', mensaje: 'Lleva efectivo' },
      })
    })

    it('escapa el id en la ruta (un id raro no cambia la URL)', async () => {
      const fetchFn = vi.fn(async () => respuesta(detalle))
      await crear(fetchFn).obtenerServicio('a/../../b?x=1', 'es')
      expect(fetchFn.mock.calls[0][0]).toBe('/api/catalog/servicios/a%2F..%2F..%2Fb%3Fx%3D1')
    })

    it('un servicio sin pagos informados trae avisoPagos nulo', async () => {
      const s = await crear(async () => respuesta({ ...detalle, aviso_pagos: null })).obtenerServicio('x', 'es')
      expect(s.avisoPagos).toBeNull()
    })

    it('el 404 del contrato es NO_ENCONTRADO', async () => {
      const e = await falla(crear(async () => respuesta({ error: 'NO_ENCONTRADO', message: 'No existe', correlation_id: 'c-1' }, { status: 404 })).obtenerServicio('x', 'es'))
      expect(e).toBeInstanceOf(CatalogError)
      expect(e).toMatchObject({ code: 'NO_ENCONTRADO', status: 404, message: 'No existe', correlationId: 'c-1' })
    })

    it('un 404 sin cuerpo (ruta que el gateway no tiene) también es NO_ENCONTRADO por el estado', async () => {
      expect((await falla(crear(async () => respuesta(undefined, { status: 404 })).obtenerServicio('x', 'es'))).code).toBe('NO_ENCONTRADO')
    })
  })

  describe('nombresServicios', () => {
    it('repite el parámetro ids, como pide el contrato', async () => {
      const fetchFn = vi.fn(async () => respuesta({ items: [{ id: 'a', nombre: 'A', activo: true }, { id: 'b', nombre: 'B', activo: false }] }))
      const r = await crear(fetchFn).nombresServicios(['a', 'b'], 'es')
      expect(fetchFn.mock.calls[0][0]).toBe('/api/catalog/servicios/nombres?ids=a&ids=b')
      expect(r).toEqual([{ id: 'a', nombre: 'A', activo: true }, { id: 'b', nombre: 'B', activo: false }])
    })
    it('ignora entradas sin id', async () => {
      expect(await crear(async () => respuesta({ items: [{ nombre: 'sin id' }, { id: 'a', nombre: 'A' }] })).nombresServicios(['a'], 'es')).toEqual([{ id: 'a', nombre: 'A', activo: true }])
    })
  })

  it('registrarIntencionVisita hace POST y acepta el 204', async () => {
    const fetchFn = vi.fn(async () => respuesta(undefined, { status: 204 }))
    await expect(crear(fetchFn).registrarIntencionVisita('abc')).resolves.toBeUndefined()
    expect(fetchFn.mock.calls[0]).toEqual(['/api/catalog/servicios/abc/intencion-visita', expect.objectContaining({ method: 'POST' })])
  })

  describe('mapaServicios', () => {
    it('pide /mapa/servicios con bbox y zoom y convierte el GeoJSON ([lon, lat])', async () => {
      const fetchFn = vi.fn(async () => respuesta({ type: 'FeatureCollection', features: [
        { type: 'Feature', geometry: { type: 'Point', coordinates: [-74.09, 11.32] }, properties: { tipo: 'servicio', id: 's1', nombre: 'Bahía', categoria: 'PLAYA', calificacion_promedio: 4.2 } },
        { type: 'Feature', geometry: { type: 'Point', coordinates: [-73.9, 11.2] }, properties: { tipo: 'grupo', conteo: 5 } },
        { type: 'Feature', geometry: null, properties: { tipo: 'servicio', id: 'roto' } },
      ] }))
      const r = await crear(fetchFn).mapaServicios({ bbox: [-75, 10, -73, 12], zoom: 10.4, categorias: ['PLAYA'], idioma: 'es' })
      const u = new URL(fetchFn.mock.calls[0][0], 'http://x')
      expect(u.pathname).toBe('/api/catalog/mapa/servicios')
      expect(Object.fromEntries(u.searchParams)).toEqual({ bbox: '-75,10,-73,12', zoom: '10', categoria: 'PLAYA' })
      expect(r).toEqual([
        { tipo: 'servicio', id: 's1', nombre: 'Bahía', categoria: 'PLAYA', calificacion: 4.2, conteo: null, lat: 11.32, lon: -74.09 },
        { tipo: 'grupo', id: undefined, nombre: undefined, categoria: undefined, calificacion: null, conteo: 5, lat: 11.2, lon: -73.9 },
      ]) // el punto sin geometría se descarta
    })
  })

  describe('errores comunes', () => {
    it('sin red es SIN_CONEXION', async () => {
      expect((await falla(crear(async () => { throw new TypeError('Failed to fetch') }).buscarServicios({ pagina: 1 }))).code).toBe('SIN_CONEXION')
    })
    it('un 400 del contrato es VALIDACION', async () => {
      expect((await falla(crear(async () => respuesta({ error: 'VALIDACION', message: 'mal', correlation_id: 'c' }, { status: 400 })).buscarServicios({ pagina: 1 }))).code).toBe('VALIDACION')
    })
    it('un 5xx sin código es ERROR con su estado', async () => {
      const e = await falla(crear(async () => respuesta(undefined, { status: 502 })).buscarServicios({ pagina: 1 }))
      expect(e).toMatchObject({ code: 'ERROR', status: 502 })
    })
  })
})
