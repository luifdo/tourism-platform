import { describe, expect, it } from 'vitest'
import { TOTAL, conjuntoPara, cuadroMasCercano, indiceDeAvance, ordenDeCarga, recorteCover, rutaDeCuadro } from '../src/lib/heroFrames.js'

describe('fotogramas de la portada', () => {
  it('la ruta lleva el conjunto y el número con tres cifras (de 1 a 120)', () => {
    expect(rutaDeCuadro('/', 'd', 0)).toBe('/hero/d/f001.webp')
    expect(rutaDeCuadro('/tourism-platform/', 'm', 119)).toBe('/tourism-platform/hero/m/f120.webp')
  })
  it('teléfono en vertical -> conjunto vertical; todo lo demás -> ancho', () => {
    expect(conjuntoPara(390, 844)).toBe('m')
    expect(conjuntoPara(844, 390)).toBe('d') // teléfono acostado
    expect(conjuntoPara(820, 1180)).toBe('d') // tableta en vertical
    expect(conjuntoPara(1440, 900)).toBe('d')
  })
  it('el avance del scroll se vuelve un cuadro, acotado', () => {
    expect(indiceDeAvance(0)).toBe(0)
    expect(indiceDeAvance(1)).toBe(TOTAL - 1)
    expect(indiceDeAvance(0.5)).toBe(Math.round((TOTAL - 1) / 2))
    expect(indiceDeAvance(-3)).toBe(0)
    expect(indiceDeAvance(9)).toBe(TOTAL - 1)
    expect(indiceDeAvance(NaN)).toBe(0)
  })
  it('el orden de carga trae todos los cuadros una vez, empezando por el inicio y el final y luego de a 16', () => {
    const o = ordenDeCarga()
    expect(o).toHaveLength(TOTAL)
    expect(new Set(o).size).toBe(TOTAL)
    expect(o.slice(0, 2)).toEqual([0, TOTAL - 1])
    expect(o.slice(2, 8)).toEqual([16, 32, 48, 64, 80, 96])
  })
  it('con ahorro de datos solo pide los múltiplos del paso y el último', () => {
    const o = ordenDeCarga(TOTAL, 4)
    expect(o.every((i) => i % 4 === 0 || i === TOTAL - 1)).toBe(true)
    expect(o).toContain(TOTAL - 1)
    expect(o.length).toBeLessThan(TOTAL / 3)
  })
  it('usa el cuadro cargado más cercano, antes o después', () => {
    const c = Array(10).fill(false); c[2] = true; c[8] = true
    expect(cuadroMasCercano(2, c)).toBe(2)
    expect(cuadroMasCercano(4, c)).toBe(2)
    expect(cuadroMasCercano(6, c)).toBe(8)
    expect(cuadroMasCercano(5, c)).toBe(2) // empate: gana el anterior
    expect(cuadroMasCercano(5, Array(10).fill(false))).toBeNull()
  })
  it('recorte tipo cover: un lienzo vertical toma el centro de un cuadro ancho', () => {
    const r = recorteCover(1280, 720, 300, 600)
    expect(r.sh).toBeCloseTo(720); expect(r.sw).toBeCloseTo(360); expect(r.sx).toBeCloseTo(460); expect(r.sy).toBeCloseTo(0)
    const w = recorteCover(1280, 720, 1600, 400) // lienzo muy ancho: toma una franja central
    expect(w.sw).toBeCloseTo(1280); expect(w.sh).toBeCloseTo(320); expect(w.sy).toBeCloseTo(200)
  })
})
