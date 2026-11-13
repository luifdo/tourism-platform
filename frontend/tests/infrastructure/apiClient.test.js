import { describe, expect, it, vi } from 'vitest'
import { createApiClient } from '../../src/infrastructure/http/apiClient.js'

const respuesta = (status, cuerpo, headers = {}) => ({ status, ok: status < 300, headers: { get: (k) => headers[k] ?? null }, json: async () => cuerpo, text: async () => String(cuerpo) })

describe('apiClient', () => {
  it('arma la URL con query sin vacíos, manda If-Match, idioma y cuerpo JSON', async () => {
    const fetchFn = vi.fn(async () => respuesta(200, { ok: 1 }, { ETag: '"3"' }))
    const api = createApiClient({ baseUrl: '/api/x', fetchFn })
    const r = await api.request('PUT', '/a', { query: { q: 'hola', vacio: '', nulo: null, n: 0 }, body: { a: 1 }, version: 3, idioma: 'en', headers: { 'Idempotency-Key': undefined } })
    expect(r).toEqual({ data: { ok: 1 }, etag: '"3"', status: 200 })
    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('/api/x/a?q=hola&n=0')
    expect(init.headers).toMatchObject({ 'If-Match': '3', 'Accept-Language': 'en', 'Content-Type': 'application/json' })
    expect(init.headers).not.toHaveProperty('Idempotency-Key')
    expect(init.signal).toBeInstanceOf(AbortSignal)
  })
  it('traduce errores de IAM (code, detail, errores) y de catalog (error, message)', async () => {
    const iam = createApiClient({ baseUrl: '', fetchFn: async () => respuesta(422, { code: 'PASSWORD_INVALIDA', detail: 'débil', errores: [{ campo: 'password_nueva', mensaje: 'corta' }] }) })
    await expect(iam.request('POST', '/x')).rejects.toMatchObject({ code: 'PASSWORD_INVALIDA', status: 422, campos: [{ campo: 'password_nueva', mensaje: 'corta' }] })
    const cat = createApiClient({ baseUrl: '', fetchFn: async () => respuesta(409, { error: 'VERSION_DISTINTA', message: 'cambió' }) })
    await expect(cat.request('PUT', '/x')).rejects.toMatchObject({ code: 'VERSION_DISTINTA', status: 409 })
  })
  it('sin código usa el estado HTTP; sin red es SIN_CONEXION; 204 devuelve null', async () => {
    const a = createApiClient({ baseUrl: '', fetchFn: async () => respuesta(403, null) })
    await expect(a.request('GET', '/x')).rejects.toMatchObject({ code: 'ROL_INSUFICIENTE' })
    const b = createApiClient({ baseUrl: '', fetchFn: async () => { throw new TypeError('x') } })
    await expect(b.request('GET', '/x')).rejects.toMatchObject({ code: 'SIN_CONEXION' })
    const c = createApiClient({ baseUrl: '', fetchFn: async () => respuesta(204, null) })
    expect((await c.request('DELETE', '/x')).data).toBeNull()
  })
  it('as: text devuelve el cuerpo sin interpretar (CSV)', async () => {
    const api = createApiClient({ baseUrl: '', fetchFn: async () => respuesta(200, 'a;b\n1;2') })
    expect((await api.request('GET', '/r', { as: 'text', aceptar: 'text/csv' })).data).toBe('a;b\n1;2')
  })
})
