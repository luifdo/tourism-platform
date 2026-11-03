import { describe, expect, it } from 'vitest'
import { ESPERA_MAXIMA_MS, MAX_MENSAJE, puedeUsarAsistente, validarMensaje } from '../../../src/domain/assistant/rules.js'

describe('reglas del mensaje al asistente', () => {
  it('rechaza un mensaje vacío o de solo espacios', () => {
    for (const t of ['', '   ', '\n\t', null, undefined]) expect(validarMensaje(t)).toEqual({ ok: false, codigo: 'MENSAJE_VACIO' })
  })

  it('quita los espacios de los bordes', () => {
    expect(validarMensaje('  hola  ')).toEqual({ ok: true, mensaje: 'hola' })
  })

  it('acepta exactamente 1000 caracteres y rechaza 1001', () => {
    expect(validarMensaje('a'.repeat(MAX_MENSAJE)).ok).toBe(true)
    expect(validarMensaje('a'.repeat(MAX_MENSAJE + 1))).toEqual({ ok: false, codigo: 'MENSAJE_LARGO' })
  })

  it('cuenta los emojis como un carácter, igual que el servicio', () => {
    expect(validarMensaje('🌊'.repeat(MAX_MENSAJE)).ok).toBe(true)
    expect(validarMensaje('🌊'.repeat(MAX_MENSAJE + 1)).ok).toBe(false)
  })

  it('solo los turistas pueden usar el asistente', () => {
    expect(puedeUsarAsistente('Turista')).toBe(true)
    for (const rol of ['Prestador', 'Admin', undefined]) expect(puedeUsarAsistente(rol)).toBe(false)
  })

  it('espera más de 45 s (el corte del servicio) pero menos de 60 s (el gateway)', () => {
    expect(ESPERA_MAXIMA_MS).toBeGreaterThanOrEqual(50_000)
    expect(ESPERA_MAXIMA_MS).toBeLessThan(60_000)
  })
})
