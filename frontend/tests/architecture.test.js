import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { describe, expect, it } from 'vitest'

/*
 * Regla de dependencias de la arquitectura hexagonal del frontend de reservas (hacia adentro):
 *
 *   UI (components, views, ui)  ──►  application  ──►  domain
 *                                        ▲
 *   infrastructure ──────────────────────┘ (implementa los puertos)
 *   composition.js: único lugar que conoce casos de uso y adaptadores a la vez.
 */
const SRC = resolve(import.meta.dirname, '../src')

const archivos = (dir) =>
  readdirSync(dir).flatMap((n) => {
    const p = join(dir, n)
    return statSync(p).isDirectory() ? archivos(p) : /\.(js|vue)$/.test(n) ? [p] : []
  })

const capaDe = (abs) => {
  const rel = relative(SRC, abs).split(sep)
  return rel.length === 1 ? rel[0].replace(/\.\w+$/, '') : rel[0] // 'domain' | 'application' | 'infrastructure' | 'components' | 'views' | 'ui' | 'lib' | 'composition' ...
}

const importsDe = (abs) => {
  const src = readFileSync(abs, 'utf8')
  const salida = []
  for (const m of src.matchAll(/(?:from|import)\s*\(?\s*['"]([^'"]+)['"]/g)) salida.push(m[1])
  return salida
}

/** Convierte un import en { capa, externo } */
const resolver = (desde, spec) => {
  if (!spec.startsWith('.')) return { externo: spec }
  return { capa: capaDe(resolve(dirname(desde), spec)) }
}

const todos = archivos(SRC)
const deCapa = (capa) => todos.filter((f) => capaDe(f) === capa)
const nombre = (f) => relative(SRC, f)

const GLOBALES_DE_PLATAFORMA = [/\bfetch\s*\(/, /\blocalStorage\b/, /\bsessionStorage\b/, /\bindexedDB\b/, /\bwindow\./, /\bdocument\./, /import\.meta\.env/, /\bnavigator\./]

describe('arquitectura hexagonal: regla de dependencias', () => {
  it('hay archivos en cada capa (la prueba no está vacía)', () => {
    for (const capa of ['domain', 'application', 'infrastructure', 'components', 'views'])
      expect(deCapa(capa).length, capa).toBeGreaterThan(0)
  })

  it('domain no importa nada fuera de domain ni de librerías', () => {
    for (const f of deCapa('domain'))
      for (const spec of importsDe(f)) {
        const r = resolver(f, spec)
        expect(r.externo, `${nombre(f)} importa la librería '${spec}'`).toBeUndefined()
        expect(r.capa, `${nombre(f)} importa de la capa '${r.capa}'`).toBe('domain')
      }
  })

  it('domain y application no tocan el navegador, la red ni el almacenamiento', () => {
    for (const f of [...deCapa('domain'), ...deCapa('application')]) {
      const codigo = readFileSync(f, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
      for (const g of GLOBALES_DE_PLATAFORMA) expect(codigo, `${nombre(f)} usa ${g}`).not.toMatch(g)
    }
  })

  it('application solo importa de domain y de application, sin librerías', () => {
    for (const f of deCapa('application'))
      for (const spec of importsDe(f)) {
        const r = resolver(f, spec)
        expect(r.externo, `${nombre(f)} importa la librería '${spec}'`).toBeUndefined()
        expect(['domain', 'application'], `${nombre(f)} importa de '${r.capa}'`).toContain(r.capa)
      }
  })

  it('infrastructure no depende de la UI, de Vue ni de la composición', () => {
    for (const f of deCapa('infrastructure'))
      for (const spec of importsDe(f)) {
        const r = resolver(f, spec)
        if (r.externo) expect(['vue', 'vue-i18n', 'vue-router'], `${nombre(f)} importa '${spec}'`).not.toContain(spec)
        else expect(['components', 'views', 'ui', 'composition'], `${nombre(f)} importa de '${r.capa}'`).not.toContain(r.capa)
      }
  })

  it('la UI no importa infrastructure: solo casos de uso (vía composition) y dominio', () => {
    for (const f of [...deCapa('components'), ...deCapa('views'), ...deCapa('ui')])
      for (const spec of importsDe(f)) {
        const r = resolver(f, spec)
        expect(r.capa, `${nombre(f)} importa directamente de infrastructure`).not.toBe('infrastructure')
        expect(r.capa, `${nombre(f)} importa directamente de application`).not.toBe('application')
      }
  })

  it('solo composition.js conecta los casos de uso con los adaptadores concretos', () => {
    const conectan = todos.filter((f) => {
      const capas = importsDe(f).map((s) => resolver(f, s).capa)
      return capas.includes('infrastructure') && capas.includes('application')
    })
    expect(conectan.map(nombre)).toEqual(['composition.js'])
  })
})
