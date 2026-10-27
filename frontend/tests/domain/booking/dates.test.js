import { describe, expect, it } from 'vitest'
import { addDays, daysInMonth, monthKey, startOfDay, today, tomorrow, weekday } from '../../../src/domain/booking/dates.js'

describe('fechas del dominio (America/Bogota)', () => {
  it('"hoy" se calcula en Bogotá, no en UTC', () => {
    // 03:00 UTC del 27 = 22:00 del 26 en Bogotá
    expect(today(new Date('2026-10-27T03:00:00Z'))).toBe('2026-10-26')
    expect(today(new Date('2026-10-27T05:00:00Z'))).toBe('2026-10-27')
  })

  it('"mañana" es el día siguiente a hoy en Bogotá', () => {
    expect(tomorrow(new Date('2026-10-27T03:00:00Z'))).toBe('2026-10-27')
  })

  it('suma días cruzando mes, año y bisiesto', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
    expect(addDays('2028-02-28', 1)).toBe('2028-02-29')
    expect(addDays('2026-11-01', -1)).toBe('2026-10-31')
  })

  it('día de la semana: 1 = lunes … 7 = domingo', () => {
    expect(weekday('2026-10-26')).toBe(1)
    expect(weekday('2026-10-31')).toBe(6)
    expect(weekday('2026-11-01')).toBe(7)
  })

  it('días del mes y clave de mes', () => {
    expect(daysInMonth('2026-02')).toBe(28)
    expect(daysInMonth('2028-02')).toBe(29)
    expect(daysInMonth('2026-10')).toBe(31)
    expect(monthKey('2026-10-27')).toBe('2026-10')
  })

  it('el día empieza a las 00:00 de Bogotá (05:00 UTC)', () => {
    expect(startOfDay('2026-10-27').toISOString()).toBe('2026-10-27T05:00:00.000Z')
  })
})
