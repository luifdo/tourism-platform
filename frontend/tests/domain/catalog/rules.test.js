import { describe, expect, it } from 'vitest'
import { CATEGORIAS, MAX_TEXTO, TAMANO_PAGINA, nivelOcupacion, normalizarBusqueda, trocear } from '../../../src/domain/catalog/rules.js'

describe('reglas del catálogo', () => {
  it('las categorías son las 7 del contrato', () => {
    expect([...CATEGORIAS].sort()).toEqual(['ALOJAMIENTO', 'AVENTURA', 'CULTURA', 'GASTRONOMIA', 'NATURALEZA', 'PLAYA', 'TRANSPORTE'])
  })

  it('normaliza la búsqueda: texto recortado, página y tamaño por defecto', () => {
    expect(normalizarBusqueda({ texto: '  playa  ' })).toEqual({ texto: 'playa', categorias: [], pagina: 1, tamano: TAMANO_PAGINA })
    expect(normalizarBusqueda()).toEqual({ texto: '', categorias: [], pagina: 1, tamano: TAMANO_PAGINA })
  })

  it('corta el texto en 200 caracteres (contrato)', () => {
    expect(normalizarBusqueda({ texto: 'a'.repeat(500) }).texto).toHaveLength(MAX_TEXTO)
  })

  it('descarta categorías inventadas y repetidas', () => {
    expect(normalizarBusqueda({ categorias: ['PLAYA', 'PLAYA', 'NO_EXISTE', 'CULTURA'] }).categorias).toEqual(['PLAYA', 'CULTURA'])
  })

  it('la página nunca baja de 1 ni acepta basura, y el tamaño tiene tope', () => {
    expect(normalizarBusqueda({ pagina: 0 }).pagina).toBe(1)
    expect(normalizarBusqueda({ pagina: -3 }).pagina).toBe(1)
    expect(normalizarBusqueda({ pagina: 'x' }).pagina).toBe(1)
    expect(normalizarBusqueda({ pagina: 3.9 }).pagina).toBe(3)
    expect(normalizarBusqueda({ tamano: 9999 }).tamano).toBe(100)
  })

  it('trocear parte una lista en tandas', () => {
    expect(trocear([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]])
    expect(trocear([], 100)).toEqual([])
    expect(trocear(Array.from({ length: 250 }, (_, i) => i), 100).map((t) => t.length)).toEqual([100, 100, 50])
  })

  it('niveles de ocupación según los umbrales de DESIGN.md', () => {
    expect([0, 59, 60, 85, 86, 100].map(nivelOcupacion)).toEqual(['ok', 'ok', 'mid', 'mid', 'high', 'high'])
  })
})
