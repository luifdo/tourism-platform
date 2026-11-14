import { describe, expect, it } from 'vitest'
import {
  ACTIVOS, cuposDisponibles, cuposReservados, decisionCancelar, decisionModificar, esDuplicada, estadoDia, estimado,
  lineaDeTiempo, liquidar, maxPersonas, plazoRespuesta, tarifaDia, validarSolicitud, ventanaReserva,
} from '../../../src/domain/booking/rules.js'

const AHORA = new Date('2026-10-26T15:00:00Z') // 10:00 del 26 de octubre en Bogotá
const reserva = (extra = {}) => ({
  id: 'r1', servicio_id: 's1', turista_id: 't1', fecha_reserva: '2026-11-05', numero_personas: 2,
  estado: 'SOLICITADA', version: 1, expira_en: '2026-10-28T15:00:00.000Z', motivo: null, ...extra,
})

describe('ventana de reserva', () => {
  it('va de mañana a 62 días en total', () => {
    expect(ventanaReserva(AHORA)).toEqual({ desde: '2026-10-27', hasta: '2026-12-27' })
  })
})

describe('plazo de respuesta del prestador', () => {
  it('es ahora + 48 h cuando la reserva es lejana', () => {
    expect(plazoRespuesta('2026-11-10', AHORA)).toBe('2026-10-28T15:00:00.000Z')
  })
  it('nunca pasa de las 00:00 del día de la reserva', () => {
    expect(plazoRespuesta('2026-10-27', AHORA)).toBe('2026-10-27T05:00:00.000Z')
    expect(plazoRespuesta('2026-10-28', AHORA)).toBe('2026-10-28T05:00:00.000Z')
  })
  it('para pasado mañana pasadas las 05:00 UTC usa el límite del día', () => {
    expect(plazoRespuesta('2026-10-29', AHORA)).toBe('2026-10-28T15:00:00.000Z')
  })
})

describe('validar solicitud', () => {
  it('acepta una solicitud correcta', () => {
    expect(validarSolicitud({ fecha: '2026-10-27', personas: 2 }, { ahora: AHORA, maxPersonas: 5 })).toEqual([])
  })
  it('rechaza hoy y fechas pasadas: se reserva desde mañana', () => {
    expect(validarSolicitud({ fecha: '2026-10-26', personas: 1 }, { ahora: AHORA })).toHaveLength(1)
    expect(validarSolicitud({ fecha: '2026-10-01', personas: 1 }, { ahora: AHORA })).toHaveLength(1)
    expect(validarSolicitud({ fecha: '', personas: 1 }, { ahora: AHORA })).toHaveLength(1)
  })
  it('exige un número entero de personas de al menos 1', () => {
    for (const personas of [0, -1, 1.5, NaN, undefined])
      expect(validarSolicitud({ fecha: '2026-10-27', personas }, { ahora: AHORA }), String(personas)).toHaveLength(1)
  })
  it('no admite más personas que los cupos', () => {
    expect(validarSolicitud({ fecha: '2026-10-27', personas: 6 }, { ahora: AHORA, maxPersonas: 5 })).toHaveLength(1)
    expect(validarSolicitud({ fecha: '2026-10-27', personas: 5 }, { ahora: AHORA, maxPersonas: 5 })).toEqual([])
  })
})

describe('modificar (UC12)', () => {
  it('solo en estado SOLICITADA', () => {
    expect(decisionModificar(reserva()).permitido).toBe(true)
    for (const estado of ['CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'FINALIZADA'])
      expect(decisionModificar(reserva({ estado })), estado).toMatchObject({ permitido: false, codigo: 'TRANSICION_INVALIDA' })
  })
})

describe('cancelar (UC12)', () => {
  const hoy = '2026-10-26'
  it('una SOLICITADA siempre se puede cancelar', () => {
    expect(decisionCancelar(reserva({ fecha_reserva: '2026-10-26' }), hoy).permitido).toBe(true)
  })
  it('una CONFIRMADA se cancela hasta el día anterior a la reserva', () => {
    expect(decisionCancelar(reserva({ estado: 'CONFIRMADA', fecha_reserva: '2026-10-27' }), hoy).permitido).toBe(true)
  })
  it('una CONFIRMADA el mismo día o después queda FUERA_DE_PLAZO', () => {
    expect(decisionCancelar(reserva({ estado: 'CONFIRMADA', fecha_reserva: '2026-10-26' }), hoy)).toMatchObject({ permitido: false, codigo: 'FUERA_DE_PLAZO' })
    expect(decisionCancelar(reserva({ estado: 'CONFIRMADA', fecha_reserva: '2026-10-20' }), hoy).codigo).toBe('FUERA_DE_PLAZO')
  })
  it('los estados finales no se cancelan', () => {
    for (const estado of ['RECHAZADA', 'CANCELADA', 'FINALIZADA'])
      expect(decisionCancelar(reserva({ estado }), hoy), estado).toMatchObject({ permitido: false, codigo: 'TRANSICION_INVALIDA' })
  })
})

describe('transiciones del sistema (liquidar)', () => {
  it('una SOLICITADA con el plazo vencido pasa a RECHAZADA y sube la versión', () => {
    const r = reserva({ expira_en: '2026-10-26T14:00:00.000Z' })
    const nueva = liquidar(r, AHORA)
    expect(nueva).toMatchObject({ estado: 'RECHAZADA', expira_en: null, version: 2 })
    expect(nueva.motivo).toMatch(/plazo/i)
    expect(r.estado).toBe('SOLICITADA') // no muta el original
  })
  it('una SOLICITADA dentro del plazo no cambia (misma referencia)', () => {
    const r = reserva({ expira_en: '2026-10-26T16:00:00.000Z' })
    expect(liquidar(r, AHORA)).toBe(r)
  })
  it('una CONFIRMADA con fecha pasada pasa a FINALIZADA', () => {
    expect(liquidar(reserva({ estado: 'CONFIRMADA', fecha_reserva: '2026-10-25' }), AHORA)).toMatchObject({ estado: 'FINALIZADA', version: 2 })
  })
  it('una CONFIRMADA de hoy o futura no cambia; los estados finales tampoco', () => {
    for (const r of [reserva({ estado: 'CONFIRMADA', fecha_reserva: '2026-10-26' }), reserva({ estado: 'CANCELADA' }), reserva({ estado: 'FINALIZADA' })])
      expect(liquidar(r, AHORA)).toBe(r)
  })
})

describe('cupos y duplicados', () => {
  const lista = [
    reserva({ id: 'a', numero_personas: 3 }),
    reserva({ id: 'b', numero_personas: 2, estado: 'CONFIRMADA' }),
    reserva({ id: 'c', numero_personas: 4, estado: 'CANCELADA' }),
    reserva({ id: 'd', numero_personas: 1, fecha_reserva: '2026-11-06' }),
    reserva({ id: 'e', numero_personas: 1, servicio_id: 's2' }),
  ]
  it('solo cuentan las reservas activas del mismo servicio y fecha', () => {
    expect(cuposReservados(lista, 's1', '2026-11-05')).toBe(5)
  })
  it('se puede excluir una reserva (al modificarla)', () => {
    expect(cuposReservados(lista, 's1', '2026-11-05', 'a')).toBe(2)
  })
  it('los cupos disponibles nunca son negativos', () => {
    expect(cuposDisponibles(10, 4)).toBe(6)
    expect(cuposDisponibles(3, 5)).toBe(0)
  })
  it('detecta una reserva activa duplicada del mismo turista', () => {
    expect(esDuplicada(lista, { turistaId: 't1', servicioId: 's1', fecha: '2026-11-05' })).toBe(true)
    expect(esDuplicada(lista, { turistaId: 't1', servicioId: 's1', fecha: '2026-11-07' })).toBe(false)
    expect(esDuplicada(lista, { turistaId: 'otro', servicioId: 's1', fecha: '2026-11-05' })).toBe(false)
  })
  it('una reserva cancelada no cuenta como duplicada', () => {
    expect(esDuplicada([reserva({ estado: 'CANCELADA' })], { turistaId: 't1', servicioId: 's1', fecha: '2026-11-05' })).toBe(false)
  })
  it('ACTIVOS son solo SOLICITADA y CONFIRMADA', () => {
    expect([...ACTIVOS]).toEqual(['SOLICITADA', 'CONFIRMADA'])
  })
})

describe('tarifa, personas y calendario', () => {
  it('usa la tarifa del día si existe y, si no, la base', () => {
    expect(tarifaDia({ tarifa_dia: 156000 }, 130000)).toBe(156000)
    expect(tarifaDia({ tarifa_dia: null }, 130000)).toBe(130000)
    expect(tarifaDia(undefined, 130000)).toBe(130000)
  })
  it('el máximo de personas son los cupos del día (1 si no hay día elegido)', () => {
    expect(maxPersonas({ cupos_disponibles: 7 })).toBe(7)
    expect(maxPersonas(undefined)).toBe(1)
  })
  it('estima el total', () => expect(estimado(130000, 3)).toBe(390000))

  const rango = { desde: '2026-10-27', hasta: '2026-12-27' }
  it('clasifica cada día del calendario', () => {
    expect(estadoDia('2026-10-26', { cupos_disponibles: 5 }, rango)).toBe('fuera')
    expect(estadoDia('2026-12-28', { cupos_disponibles: 5 }, rango)).toBe('fuera')
    expect(estadoDia('2026-11-02', undefined, rango)).toBe('cerrado')
    expect(estadoDia('2026-11-03', { cupos_disponibles: 0 }, rango)).toBe('agotado')
    expect(estadoDia('2026-11-04', { cupos_disponibles: 3 }, rango)).toBe('ok')
  })
})

describe('línea de tiempo', () => {
  const marcas = (estado) => lineaDeTiempo(reserva({ estado })).map((p) => `${p.estado}:${p.alcanzado ? 1 : 0}${p.negativo ? '!' : ''}`)
  it('SOLICITADA solo alcanzó el primer paso', () => expect(marcas('SOLICITADA')).toEqual(['SOLICITADA:1', 'CONFIRMADA:0', 'FINALIZADA:0']))
  it('CONFIRMADA alcanzó dos pasos', () => expect(marcas('CONFIRMADA')).toEqual(['SOLICITADA:1', 'CONFIRMADA:1', 'FINALIZADA:0']))
  it('FINALIZADA alcanzó los tres', () => expect(marcas('FINALIZADA')).toEqual(['SOLICITADA:1', 'CONFIRMADA:1', 'FINALIZADA:1']))
  it('RECHAZADA y CANCELADA reemplazan el paso medio y se marcan como negativos', () => {
    expect(marcas('RECHAZADA')).toEqual(['SOLICITADA:1', 'RECHAZADA:1!', 'FINALIZADA:0'])
    expect(marcas('CANCELADA')).toEqual(['SOLICITADA:1', 'CANCELADA:1!', 'FINALIZADA:0'])
  })
})
