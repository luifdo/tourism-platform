import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import es from '../src/locales/es.js'
import en from '../src/locales/en.js'
import gestionEs from '../src/locales/gestion.es.js'
import gestionEn from '../src/locales/gestion.en.js'

/* Los dos idiomas tienen las mismas claves, y toda clave fija que el código pide existe (una clave que falta se vería como texto técnico en pantalla). */
const SRC = resolve(import.meta.dirname, '../src')
const ES = { ...es, ...gestionEs }
const EN = { ...en, ...gestionEn }

const claves = (o, pre = '') => Object.entries(o).flatMap(([k, v]) => (v && typeof v === 'object' && !Array.isArray(v) ? claves(v, `${pre}${k}.`) : [`${pre}${k}`]))
const archivos = (d) => readdirSync(d).flatMap((n) => { const p = join(d, n); return statSync(p).isDirectory() ? archivos(p) : /\.(vue|js)$/.test(n) && !n.includes('locales') ? [p] : [] })

describe('textos de la interfaz', () => {
  it('español e inglés tienen exactamente las mismas claves', () => {
    const a = claves(ES).sort(); const b = claves(EN).sort()
    expect(a.filter((k) => !b.includes(k)), 'faltan en inglés').toEqual([])
    expect(b.filter((k) => !a.includes(k)), 'faltan en español').toEqual([])
  })

  it('toda clave fija que usa el código existe', () => {
    const existentes = new Set(claves(ES))
    // una clave "padre" (un objeto o lista) también vale: t('x.y') puede pedir un bloque entero con tm()
    const prefijos = new Set([...existentes].flatMap((k) => k.split('.').map((_, i, p) => p.slice(0, i + 1).join('.'))))
    const faltan = []
    for (const f of archivos(SRC)) {
      const src = readFileSync(f, 'utf8')
      for (const m of src.matchAll(/(?<![\w.$])(?:t|te|tm)\(\s*'([a-zA-Z][\w.]*)'/g)) if (!prefijos.has(m[1])) faltan.push(`${f.replace(SRC, '')}: ${m[1]}`)
    }
    expect(faltan).toEqual([])
  })
})
