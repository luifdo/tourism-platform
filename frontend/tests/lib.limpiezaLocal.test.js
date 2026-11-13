import { describe, expect, it, vi } from 'vitest'
import { CACHES_OBSOLETAS, borrarCachesObsoletas } from '../src/lib/limpiezaLocal.js'
import { registrarError, errorGlobal, descartarError } from '../src/lib/errorGlobal.js'
import { nuevaClave } from '../src/domain/gestion/rules.js'
import { urlMapa } from '../src/ui/format.js'

describe('limpieza de cachés obsoletas', () => {
  it('borra la caché «catalogo» (traía rutas privadas) y «fuentes»', async () => {
    const almacen = { delete: vi.fn(async () => true) }
    await borrarCachesObsoletas(almacen)
    expect(CACHES_OBSOLETAS).toEqual(['catalogo', 'fuentes'])
    expect(almacen.delete.mock.calls.map((c) => c[0]).sort()).toEqual(['catalogo', 'fuentes'])
  })
  it('sin Cache Storage (HTTP no seguro) no falla, y un error al borrar tampoco', async () => {
    await expect(borrarCachesObsoletas(undefined)).resolves.toBeUndefined()
    await expect(borrarCachesObsoletas({ delete: vi.fn(async () => { throw new Error('x') }) })).resolves.toBeUndefined()
  })
})

describe('política de la caché del Service Worker', () => {
  // Misma expresión que vite.config.js: se prueba que las rutas privadas del catálogo NO la cumplan
  const publica = /^\/api\/catalog\/(servicios(\/[^/]+)?|buscar|zonas|alertas|mapa\/[^/]+)$/
  it.each(['/api/catalog/servicios', '/api/catalog/servicios/abc', '/api/catalog/servicios/nombres', '/api/catalog/buscar', '/api/catalog/zonas', '/api/catalog/alertas', '/api/catalog/mapa/servicios', '/api/catalog/mapa/zonas'])('cachea %s', (r) => expect(publica.test(r)).toBe(true))
  it.each(['/api/catalog/prestador/metricas', '/api/catalog/prestador/servicios', '/api/catalog/prestador/perfil', '/api/catalog/entidad/alertas', '/api/catalog/analitica/tablero', '/api/catalog/analitica/reportes/demanda', '/api/catalog/geocodificar', '/api/catalog/servicios/abc/otra', '/api/catalog/servicios/../prestador/perfil'])('NO cachea %s', (r) => expect(publica.test(r)).toBe(false))
  it('vite.config.js usa esa misma expresión y excluye lo que lleva Authorization', async () => {
    const { readFileSync } = await import('node:fs')
    const cfg = readFileSync(new URL('../vite.config.js', import.meta.url), 'utf8')
    expect(cfg).toContain("!request.headers.has('Authorization')")
    expect(cfg).toContain(String(publica))
    expect(cfg).toContain('catalogo-publico-v2')
  })
})

describe('errores sin atrapar', () => {
  it('guardan una referencia, ignoran las cancelaciones y se pueden descartar', () => {
    const consola = vi.spyOn(console, 'error').mockImplementation(() => {})
    registrarError(Object.assign(new Error('x'), { name: 'AbortError' }))
    registrarError(new TypeError("Failed to register a ServiceWorker for scope ('http://x/')"))
    registrarError(new TypeError('Failed to fetch'))
    expect(errorGlobal.hay).toBe(false)
    registrarError(new Error('boom'))
    expect(errorGlobal.hay).toBe(true)
    expect(errorGlobal.referencia).toMatch(/^[0-9A-Z]+-[0-9A-Z]+$/)
    descartarError()
    expect(errorGlobal.hay).toBe(false)
    consola.mockRestore()
  })
})

describe('Idempotency-Key en contextos no seguros', () => {
  it('usa randomUUID si existe y, si no, arma un UUID v4 con getRandomValues', () => {
    expect(nuevaClave({ randomUUID: () => 'fijo' })).toBe('fijo')
    const k = nuevaClave({ getRandomValues: (b) => { b.fill(0xab); return b } })
    expect(k).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
    expect(new Set([nuevaClave(globalThis.crypto), nuevaClave(globalThis.crypto)]).size).toBe(2)
  })
})

describe('urlMapa', () => {
  it('solo deja números en la dirección', () => {
    expect(urlMapa({ lat: 11.2, lon: '-74.1' })).toBe('https://www.openstreetmap.org/?mlat=11.2&mlon=-74.1#map=16/11.2/-74.1')
    expect(urlMapa({ lat: '1&x=<script>', lon: 2 })).toBe('https://www.openstreetmap.org/')
  })
})
