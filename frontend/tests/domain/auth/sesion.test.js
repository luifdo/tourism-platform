import { describe, expect, it } from 'vitest'
import { crearSesion, estadoSesion, puedeRenovar, sesionActiva, sesionVigente, vencerSesion } from '../../../src/domain/auth/rules.js'

const T0 = new Date('2026-11-12T12:00:00Z')
const en = (ms) => new Date(T0.getTime() + ms)
const respuesta = { access_token: 'a1', expires_in: 900, refresh_token: 'r1', refresh_expires_in: 604_800, usuario: { id: 'u1' } }
const sesion = crearSesion(respuesta, T0)

describe('sesión con refresh token', () => {
  it('guarda el refresh y su vencimiento (7 días) junto al access (15 min)', () => {
    expect(sesion).toEqual({ token: 'a1', usuario: { id: 'u1' }, expiraEn: T0.getTime() + 900_000, refreshToken: 'r1', refreshExpiraEn: T0.getTime() + 604_800_000 })
  })

  it('una respuesta sin refresh (servicio antiguo) deja la sesión sin cómo renovarse', () => {
    const s = crearSesion({ ...respuesta, refresh_token: undefined }, T0)
    expect(s).toMatchObject({ refreshToken: null, refreshExpiraEn: 0 })
    expect(puedeRenovar(s, T0)).toBe(false)
  })

  it('puede renovarse mientras falte más que el margen de 30 s para que venza el refresh', () => {
    expect(puedeRenovar(sesion, T0)).toBe(true)
    expect(puedeRenovar(sesion, en(604_800_000 - 31_000))).toBe(true)
    expect(puedeRenovar(sesion, en(604_800_000 - 30_000))).toBe(false)
    expect(puedeRenovar(null, T0)).toBe(false)
  })

  it('los cuatro estados: vigente, renovable, vencida y ninguna', () => {
    expect(estadoSesion(null, T0)).toBe('ninguna')
    expect(estadoSesion(sesion, T0)).toBe('vigente')
    expect(estadoSesion(sesion, en(900_000))).toBe('renovable') // venció el access, el refresh sirve
    expect(estadoSesion(sesion, en(8 * 24 * 3600_000))).toBe('vencida') // pasaron 8 días
    expect(estadoSesion({ ...sesion, refreshToken: null, refreshExpiraEn: 0 }, en(900_000))).toBe('vencida') // sin refresh no hay cómo seguir
  })

  it('la persona sigue dentro si el access sirve o si se puede renovar', () => {
    expect(sesionActiva(sesion, T0)).toBe(true)
    expect(sesionActiva(sesion, en(900_000))).toBe(true)
    expect(sesionActiva(sesion, en(8 * 24 * 3600_000))).toBe(false)
    expect(sesionActiva(null, T0)).toBe(false)
  })

  it('vencer la sesión borra los dos tokens pero recuerda quién era', () => {
    const v = vencerSesion(sesion)
    expect(v).toEqual({ token: null, usuario: { id: 'u1' }, expiraEn: 0, refreshToken: null, refreshExpiraEn: 0 })
    expect(sesionVigente(v, T0)).toBe(false)
    expect(estadoSesion(v, T0)).toBe('vencida')
    expect(sesion.refreshToken).toBe('r1') // no muta la original
  })
})
