import { describe, expect, it } from 'vitest'
import {
  MAX_DIAS_RANGO, decisionConfirmar, decisionRechazar, diasDelRango, horasRestantes, resumenCalendario, urgencia, validarDia, validarMotivo, validarRango, ventanaCalendario,
} from '../../../src/domain/booking/prestador.js'

const AHORA = new Date('2026-11-12T15:00:00Z') // 10:00 del 12 de noviembre en Bogotá
const en = (h) => new Date(AHORA.getTime() + h * 3600e3).toISOString()
const solicitud = (extra = {}) => ({ id: 'r1', estado: 'SOLICITADA', expira_en: en(10), ...extra })
const codigos = (errores) => errores.map((e) => `${e.campo}:${e.codigo}`)

describe('motivo del rechazo', () => {
  it('exige de 3 a 500 caracteres, sin contar los espacios de los bordes', () => {
    expect(validarMotivo('  ab  ').ok).toBe(false)
    expect(validarMotivo('abc')).toEqual({ ok: true, motivo: 'abc' })
    expect(validarMotivo('a'.repeat(500)).ok).toBe(true)
    expect(validarMotivo('a'.repeat(501)).ok).toBe(false)
    expect(validarMotivo(null).ok).toBe(false)
    expect(validarMotivo('').codigo).toBe('MOTIVO_INVALIDO')
  })
})

describe('confirmar y rechazar (UC20)', () => {
  it('se confirma una solicitud pendiente dentro del plazo', () => {
    expect(decisionConfirmar(solicitud(), AHORA).permitido).toBe(true)
  })
  it('no se confirma una vencida: PLAZO_VENCIDO', () => {
    expect(decisionConfirmar(solicitud({ expira_en: en(-1) }), AHORA)).toMatchObject({ permitido: false, codigo: 'PLAZO_VENCIDO' })
    expect(decisionConfirmar(solicitud({ expira_en: AHORA.toISOString() }), AHORA).permitido).toBe(false) // justo al vencer ya no
  })
  it('solo las SOLICITADA se confirman o se rechazan: TRANSICION_INVALIDA', () => {
    for (const estado of ['CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'FINALIZADA']) {
      expect(decisionConfirmar(solicitud({ estado }), AHORA)).toMatchObject({ permitido: false, codigo: 'TRANSICION_INVALIDA' })
      expect(decisionRechazar(solicitud({ estado }))).toMatchObject({ permitido: false, codigo: 'TRANSICION_INVALIDA' })
    }
    expect(decisionRechazar(solicitud()).permitido).toBe(true)
  })
  it('rechazar no depende del plazo (también se puede rechazar una que está por vencer)', () => {
    expect(decisionRechazar(solicitud({ expira_en: en(0.1) })).permitido).toBe(true)
  })
})

describe('urgencia', () => {
  it('urgente a 6 horas o menos, vencida si ya pasó, normal si hay tiempo, null si no espera respuesta', () => {
    expect(urgencia(solicitud({ expira_en: en(6) }), AHORA)).toBe('urgente')
    expect(urgencia(solicitud({ expira_en: en(6.1) }), AHORA)).toBe('normal')
    expect(urgencia(solicitud({ expira_en: en(-0.5) }), AHORA)).toBe('vencida')
    expect(urgencia(solicitud({ estado: 'CONFIRMADA' }), AHORA)).toBeNull()
    expect(urgencia(solicitud({ expira_en: null }), AHORA)).toBeNull()
    expect(horasRestantes(solicitud({ expira_en: en(3) }), AHORA)).toBeCloseTo(3)
  })
})

describe('rango de días (UC19)', () => {
  const base = { desde: '2026-11-13', hasta: '2026-11-19', cuposTotales: 10, tarifaDia: null }

  it('cuenta los días que se abrirían según los días de la semana (1 = lunes)', () => {
    expect(diasDelRango(base)).toHaveLength(7)
    expect(diasDelRango({ ...base, diasSemana: [6, 7] })).toEqual(['2026-11-14', '2026-11-15']) // sábado y domingo
    expect(diasDelRango({ desde: '2026-11-13', hasta: '2026-11-12' })).toEqual([])
  })

  it('un rango válido no tiene problemas', () => {
    expect(validarRango(base, { ahora: AHORA })).toEqual([])
    expect(validarRango({ ...base, diasSemana: [1, 3, 5] }, { ahora: AHORA, aforo: 10 })).toEqual([])
  })

  it('no puede empezar en el pasado, ni terminar antes de empezar, ni pasar de 366 días', () => {
    expect(codigos(validarRango({ ...base, desde: '2026-11-11' }, { ahora: AHORA }))).toContain('desde:FECHA_PASADA')
    expect(codigos(validarRango({ ...base, hasta: '2026-11-12' }, { ahora: AHORA }))).toContain('hasta:RANGO_INVERTIDO')
    expect(validarRango({ ...base, hasta: '2027-11-14' }, { ahora: AHORA })).toEqual([]) // 366 días después: el máximo
    expect(codigos(validarRango({ ...base, hasta: '2027-11-15' }, { ahora: AHORA }))).toContain('hasta:RANGO_MUY_LARGO')
    expect(MAX_DIAS_RANGO).toBe(366)
  })

  it('pide las fechas', () => {
    expect(codigos(validarRango({ ...base, desde: '', hasta: '' }, { ahora: AHORA }))).toEqual(['desde:FECHA_REQUERIDA', 'hasta:FECHA_REQUERIDA'])
  })

  it('los días de la semana deben ser del 1 al 7, sin repetir, y alguno debe caer en el rango', () => {
    expect(codigos(validarRango({ ...base, diasSemana: [0, 8] }, { ahora: AHORA }))).toContain('diasSemana:DIAS_INVALIDOS')
    expect(codigos(validarRango({ ...base, diasSemana: [1, 1] }, { ahora: AHORA }))).toContain('diasSemana:DIAS_INVALIDOS')
    expect(codigos(validarRango({ ...base, hasta: '2026-11-13', diasSemana: [1] }, { ahora: AHORA }))).toContain('diasSemana:RANGO_SIN_DIAS') // el 13 es viernes
  })

  it('los cupos son un entero de al menos 1 y no superan el aforo oficial', () => {
    for (const cuposTotales of [0, -1, 1.5, '3', null]) expect(codigos(validarRango({ ...base, cuposTotales }, { ahora: AHORA }))).toContain('cuposTotales:CUPOS_INVALIDOS')
    expect(codigos(validarRango({ ...base, cuposTotales: 11 }, { ahora: AHORA, aforo: 10 }))).toContain('cuposTotales:SUPERA_AFORO')
    expect(validarRango({ ...base, cuposTotales: 11 }, { ahora: AHORA })).toEqual([]) // sin aforo conocido decide el servidor
  })

  it('la tarifa es nula o un número no negativo', () => {
    expect(validarRango({ ...base, tarifaDia: 0 }, { ahora: AHORA })).toEqual([])
    expect(validarRango({ ...base, tarifaDia: 85000 }, { ahora: AHORA })).toEqual([])
    for (const tarifaDia of [-1, NaN, '5000']) expect(codigos(validarRango({ ...base, tarifaDia }, { ahora: AHORA }))).toContain('tarifaDia:TARIFA_INVALIDA')
  })
})

describe('un día del calendario (UC19)', () => {
  it('puede tener 0 cupos (cerrado) y no baja de lo ya reservado ni sube del aforo', () => {
    expect(validarDia({ cuposTotales: 0 })).toEqual([])
    expect(validarDia({ cuposTotales: 8 }, { reservados: 8, aforo: 10 })).toEqual([])
    expect(codigos(validarDia({ cuposTotales: 7 }, { reservados: 8 }))).toEqual(['cuposTotales:CUPOS_COMPROMETIDOS'])
    expect(codigos(validarDia({ cuposTotales: 11 }, { aforo: 10 }))).toEqual(['cuposTotales:SUPERA_AFORO'])
    expect(codigos(validarDia({ cuposTotales: -1 }))).toEqual(['cuposTotales:CUPOS_INVALIDOS'])
    expect(codigos(validarDia({ cuposTotales: 2, tarifaDia: -5 }))).toEqual(['tarifaDia:TARIFA_INVALIDA'])
  })

  it('la ventana por defecto va de mañana a 30 días', () => {
    expect(ventanaCalendario(AHORA)).toEqual({ desde: '2026-11-13', hasta: '2026-12-12' })
  })

  it('resume los días: abiertos, cerrados, reservados y libres', () => {
    expect(resumenCalendario([
      { cupos_totales: 10, cupos_reservados: 3, cupos_disponibles: 7 }, { cupos_totales: 0, cupos_reservados: 0, cupos_disponibles: 0 }, { cupos_totales: 5, cupos_reservados: 5, cupos_disponibles: 0 },
    ])).toEqual({ abiertos: 2, cerrados: 1, reservados: 8, disponibles: 7 })
  })
})
