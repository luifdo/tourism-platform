import { describe, expect, it, vi } from 'vitest'
import { createHttpAccountGateway, createHttpAdminGateway, createHttpEntityGateway, createHttpOfferGateway, createHttpReviewGateway } from '../../src/infrastructure/gestion/httpGestionGateways.js'
import { assertAccountGateway, assertAdminGateway, assertEntityGateway, assertOfferGateway, assertReviewGateway } from '../../src/application/gestion/ports.js'

const res = (status, cuerpo, extra = {}) => ({ status, ok: status < 300, headers: { get: () => null }, json: async () => cuerpo, text: async () => String(cuerpo), ...extra })
const espia = (cuerpo = {}, status = 200) => { const f = vi.fn(async () => res(status, cuerpo)); return f }
const llamada = (f, i = 0) => ({ url: f.mock.calls[i][0], ...f.mock.calls[i][1] })

describe('adaptadores HTTP de gestión', () => {
  it('cumplen los puertos', () => {
    assertAccountGateway(createHttpAccountGateway({ fetchFn: espia() })); assertAdminGateway(createHttpAdminGateway({ fetchFn: espia() })); assertReviewGateway(createHttpReviewGateway({ fetchFn: espia() }))
    assertOfferGateway(createHttpOfferGateway({ fetchFn: espia() })); assertEntityGateway(createHttpEntityGateway({ fetchFn: espia() }))
  })

  it('IAM: perfil, contraseña con los nombres del contrato y documentos multipart', async () => {
    const f = espia({})
    const g = createHttpAccountGateway({ fetchFn: f })
    await g.editarPerfil({ nombre: 'Ana' }); expect(llamada(f)).toMatchObject({ url: '/api/iam/perfil', method: 'PATCH', body: '{"nombre":"Ana"}' })
    await g.cambiarContrasena({ actual: 'a', nueva: 'b' }); expect(JSON.parse(llamada(f, 1).body)).toEqual({ password_actual: 'a', password_nueva: 'b' })
    await g.suprimirDatos('pw'); expect(llamada(f, 2)).toMatchObject({ url: '/api/iam/perfil', method: 'DELETE', body: '{"password":"pw"}' })
    const archivo = new Blob(['x'], { type: 'application/pdf' })
    await g.subirDocumento({ tipo: 'RUT', archivo, razonSocial: 'Guías' })
    const c = llamada(f, 3)
    expect(c).toMatchObject({ url: '/api/iam/prestador/documentos', method: 'POST' })
    expect(c.body).toBeInstanceOf(FormData)
    expect(c.body.get('tipo')).toBe('RUT'); expect(c.body.get('razon_social')).toBe('Guías')
    expect(c.headers).not.toHaveProperty('Content-Type') // el navegador pone el boundary
  })

  it('IAM admin: filtros en la URL, rechazo con documentos', async () => {
    const f = espia({})
    const g = createHttpAdminGateway({ fetchFn: f })
    await g.usuarios({ q: 'ana', rol: 'Prestador', activo: false, pagina: 2, tamano: 15 }); expect(llamada(f).url).toBe('/api/iam/admin/usuarios?q=ana&rol=Prestador&activo=false&pagina=2&tamano=15')
    await g.rechazarPrestador('u1', [{ tipo: 'RNT', motivo: 'x' }]); expect(llamada(f, 1)).toMatchObject({ url: '/api/iam/admin/prestadores/u1/rechazar', body: '{"documentos":[{"tipo":"RNT","motivo":"x"}]}' })
    await g.urlDocumento('d1'); expect(llamada(f, 2).url).toBe('/api/iam/admin/documentos/d1/url')
  })

  it('reseñas: Idempotency-Key al escribir, If-Match al editar, idioma en las lecturas', async () => {
    const f = espia({})
    const g = createHttpReviewGateway({ fetchFn: f })
    await g.escribir({ servicio_id: 's', puntuacion: 5 }, 'clave'); expect(llamada(f).headers['Idempotency-Key']).toBe('clave')
    await g.editar('r1', { puntuacion: 4 }, 3); expect(llamada(f, 1)).toMatchObject({ url: '/api/reviews/resenas/r1', method: 'PUT' }); expect(llamada(f, 1).headers['If-Match']).toBe('3')
    await g.responder('r1', 'Gracias', 4); expect(llamada(f, 2)).toMatchObject({ url: '/api/reviews/resenas/r1/respuesta', body: '{"texto":"Gracias"}' })
    await g.resenasDeServicio('s1', { orden: 'mejores', pagina: 1, tamano: 5, idioma: 'en' }); expect(llamada(f, 3).url).toBe('/api/reviews/servicios/s1/resenas?orden=mejores&pagina=1&tamano=5'); expect(llamada(f, 3).headers['Accept-Language']).toBe('en')
    await g.moderar('r1', { decision: 'PUBLICAR' }, 2); expect(llamada(f, 4).url).toBe('/api/reviews/resenas/r1/moderacion')
    await g.colaModeracion({ estado: 'EN_REVISION', pagina: 1, tamano: 10 }); expect(llamada(f, 5).url).toBe('/api/reviews/moderacion/resenas?estado=EN_REVISION&pagina=1&tamano=10')
  })

  it('catalog oferta: crear con clave, editar con versión, desactivar', async () => {
    const f = espia({})
    const g = createHttpOfferGateway({ fetchFn: f })
    await g.crearServicio({ a: 1 }, 'k'); expect(llamada(f)).toMatchObject({ url: '/api/catalog/servicios', method: 'POST' }); expect(llamada(f).headers['Idempotency-Key']).toBe('k')
    await g.editarServicio('s1', { a: 2 }, 4, 'k2'); expect(llamada(f, 1)).toMatchObject({ url: '/api/catalog/servicios/s1', method: 'PUT' }); expect(llamada(f, 1).headers['If-Match']).toBe('4')
    await g.desactivarServicio('s1', 5); expect(llamada(f, 2)).toMatchObject({ url: '/api/catalog/servicios/s1/desactivar', method: 'POST' })
    await g.metricas({ desde: '2026-10-01', hasta: '2026-10-31' }); expect(llamada(f, 3).url).toBe('/api/catalog/prestador/metricas?desde=2026-10-01&hasta=2026-10-31')
  })

  it('subir imagen: pide la URL firmada y sube el archivo con su tipo, sin Authorization', async () => {
    const f = vi.fn(async () => res(201, { subida_url: 'https://s3.x/b/k?sig=1', url_publica: 'https://s3.x/b/k', expira_en: 'x' }))
    const subir = vi.fn(async () => res(200, null))
    const g = createHttpOfferGateway({ fetchFn: f, subirFn: subir })
    const foto = new Blob(['x'], { type: 'image/png' })
    expect(await g.subirImagen(foto)).toBe('https://s3.x/b/k')
    expect(JSON.parse(llamada(f).body)).toEqual({ content_type: 'image/png', tamano_bytes: 1 })
    const [url, init] = subir.mock.calls[0]
    expect(url).toBe('https://s3.x/b/k?sig=1'); expect(init).toMatchObject({ method: 'PUT', headers: { 'Content-Type': 'image/png' } }); expect(init.headers).not.toHaveProperty('Authorization')
  })

  it('subir imagen: un rechazo del almacenamiento es SUBIDA_RECHAZADA', async () => {
    const g = createHttpOfferGateway({ fetchFn: async () => res(201, { subida_url: 'u', url_publica: 'p' }), subirFn: async () => res(403, null) })
    await expect(g.subirImagen(new Blob(['x'], { type: 'image/png' }))).rejects.toMatchObject({ code: 'SUBIDA_RECHAZADA', status: 403 })
  })

  it('Entidad: alertas, analítica y CSV como texto con nombre de archivo', async () => {
    const f = vi.fn(async (url) => (url.includes('reportes') ? res(200, 'Fecha;Zona\r\n') : res(200, {})))
    const g = createHttpEntityGateway({ fetchFn: f })
    await g.alertas({ estado: 'VIGENTE', pagina: 1, tamano: 10, idioma: 'es' }); expect(llamada(f).url).toBe('/api/catalog/entidad/alertas?estado=VIGENTE&pagina=1&tamano=10')
    await g.editarAlerta('a1', { nivel: 'CRITICA' }, 2); expect(llamada(f, 1).headers['If-Match']).toBe('2')
    await g.retirarAlerta('a1'); expect(llamada(f, 2).url).toBe('/api/catalog/alertas/a1/desactivar')
    await g.tablero({ desde: '2026-11-01', hasta: '2026-11-07', idioma: 'en' }); expect(llamada(f, 3).url).toBe('/api/catalog/analitica/tablero?desde=2026-11-01&hasta=2026-11-07')
    const r = await g.reporteCsv({ desde: '2026-11-01', hasta: '2026-11-07', zona: 'minca' })
    expect(llamada(f, 4).url).toBe('/api/catalog/analitica/reportes/demanda?desde=2026-11-01&hasta=2026-11-07&zona=minca&formato=csv')
    expect(r).toEqual({ texto: 'Fecha;Zona\r\n', nombre: 'demanda_2026-11-01_2026-11-07_minca.csv' })
  })
})
