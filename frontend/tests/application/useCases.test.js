import { beforeEach, describe, expect, it, vi } from 'vitest'
import { BookingError } from '../../src/domain/booking/errors.js'
import { createBookingUseCases } from '../../src/application/booking/useCases.js'
import { assertBookingGateway, BOOKING_GATEWAY_METHODS } from '../../src/application/booking/ports.js'

const AHORA = new Date('2026-10-26T15:00:00Z') // 26 de octubre, 10:00 en Bogotá
const reserva = (extra = {}) => ({
  id: 'r1', servicio_id: 's1', turista_id: 't1', fecha_reserva: '2026-11-05', numero_personas: 2,
  estado: 'SOLICITADA', version: 3, expira_en: '2026-10-28T15:00:00.000Z', ...extra,
})

let gateway, session, cache, clock, uc
beforeEach(() => {
  gateway = {
    consultarDisponibilidad: vi.fn(async (servicio_id) => ({ servicio_id, dias: [] })),
    solicitarReserva: vi.fn(async (body) => ({ data: reserva({ ...body, id: 'nueva' }), etag: '"1"' })),
    misReservas: vi.fn(async () => ({ items: [reserva()], pagina: 1, tamano: 20, total: 1 })),
    modificarReserva: vi.fn(async (id, version, cambios) => ({ data: reserva({ ...cambios, version: version + 1 }), etag: `"${version + 1}"` })),
    cancelarReserva: vi.fn(async () => ({ data: reserva({ estado: 'CANCELADA' }), etag: '"4"' })),
  }
  session = { isAuthenticated: vi.fn(() => true) }
  cache = { read: vi.fn(async () => null), write: vi.fn(async () => {}) }
  clock = { now: () => AHORA }
  uc = createBookingUseCases({ gateway, session, cache, clock })
})

const falla = async (promesa) => { try { await promesa } catch (e) { return e } throw new Error('se esperaba un error') }

describe('puerto BookingGateway', () => {
  it('rechaza un adaptador incompleto indicando qué le falta', () => {
    expect(() => assertBookingGateway({ consultarDisponibilidad() {} })).toThrow(/solicitarReserva/)
    expect(() => createBookingUseCases({ gateway: {}, session, cache, clock })).toThrow(TypeError)
  })
  it('acepta uno completo', () => {
    const completo = Object.fromEntries(BOOKING_GATEWAY_METHODS.map((m) => [m, () => {}]))
    expect(assertBookingGateway(completo)).toBe(completo)
  })
})

describe('reloj', () => {
  it('hoy, mañana y la ventana salen del reloj inyectado', () => {
    expect(uc.hoy()).toBe('2026-10-26')
    expect(uc.manana()).toBe('2026-10-27')
    expect(uc.ventana()).toEqual({ desde: '2026-10-27', hasta: '2026-12-27' })
  })
})

describe('consultarDisponibilidad (UC10)', () => {
  it('consulta la ventana de reserva y la devuelve junto al resultado', async () => {
    const r = await uc.consultarDisponibilidad('s1')
    expect(gateway.consultarDisponibilidad).toHaveBeenCalledWith('s1', '2026-10-27', '2026-12-27')
    expect(r).toMatchObject({ servicio_id: 's1', desde: '2026-10-27', hasta: '2026-12-27' })
  })
})

describe('solicitarReserva (UC11)', () => {
  const datos = { servicioId: 's1', fecha: '2026-11-05', personas: 2, idempotencyKey: 'clave-1' }

  it('sin sesión devuelve NO_AUTENTICADO y no llama al backend', async () => {
    session.isAuthenticated.mockReturnValue(false)
    const e = await falla(uc.solicitarReserva(datos))
    expect(e).toBeInstanceOf(BookingError)
    expect(e.code).toBe('NO_AUTENTICADO')
    expect(gateway.solicitarReserva).not.toHaveBeenCalled()
  })

  it('valida antes de llamar: fecha de hoy', async () => {
    const e = await falla(uc.solicitarReserva({ ...datos, fecha: '2026-10-26' }))
    expect(e.code).toBe('VALIDACION')
    expect(gateway.solicitarReserva).not.toHaveBeenCalled()
  })

  it('valida antes de llamar: más personas que los cupos', async () => {
    const e = await falla(uc.solicitarReserva({ ...datos, personas: 6, maxPersonas: 5 }))
    expect(e.code).toBe('VALIDACION')
    expect(gateway.solicitarReserva).not.toHaveBeenCalled()
  })

  it('envía el cuerpo del contrato con la Idempotency-Key y devuelve la reserva con su ETag', async () => {
    const r = await uc.solicitarReserva({ ...datos, maxPersonas: 5 })
    expect(gateway.solicitarReserva).toHaveBeenCalledWith({ servicio_id: 's1', fecha_reserva: '2026-11-05', numero_personas: 2 }, 'clave-1')
    expect(r.reserva.id).toBe('nueva')
    expect(r.etag).toBe('"1"')
  })

  it('propaga los errores del backend sin cambiarlos', async () => {
    gateway.solicitarReserva.mockRejectedValue(new BookingError('CUPOS_INSUFICIENTES', 'Solo quedan 1 cupos.', { status: 409 }))
    const e = await falla(uc.solicitarReserva(datos))
    expect(e).toMatchObject({ code: 'CUPOS_INSUFICIENTES', status: 409 })
  })
})

describe('modificarReserva (UC12)', () => {
  it('no llama al backend si la reserva no está SOLICITADA', async () => {
    const e = await falla(uc.modificarReserva(reserva({ estado: 'CONFIRMADA' }), { numero_personas: 3 }))
    expect(e.code).toBe('TRANSICION_INVALIDA')
    expect(gateway.modificarReserva).not.toHaveBeenCalled()
  })

  it('valida los cambios antes de llamar', async () => {
    const e = await falla(uc.modificarReserva(reserva(), { fecha_reserva: '2026-10-26' }))
    expect(e.code).toBe('VALIDACION')
    expect(gateway.modificarReserva).not.toHaveBeenCalled()
  })

  it('envía la versión que el usuario vio (If-Match) y devuelve la reserva nueva', async () => {
    const r = await uc.modificarReserva(reserva({ version: 3 }), { numero_personas: 4 })
    expect(gateway.modificarReserva).toHaveBeenCalledWith('r1', 3, { numero_personas: 4 })
    expect(r.reserva.version).toBe(4)
    expect(r.etag).toBe('"4"')
  })
})

describe('cancelarReserva (UC12)', () => {
  it('una CONFIRMADA de hoy ya no se puede cancelar y no llama al backend', async () => {
    const e = await falla(uc.cancelarReserva(reserva({ estado: 'CONFIRMADA', fecha_reserva: '2026-10-26' })))
    expect(e.code).toBe('FUERA_DE_PLAZO')
    expect(gateway.cancelarReserva).not.toHaveBeenCalled()
  })
  it('una reserva ya cancelada no se cancela otra vez', async () => {
    const e = await falla(uc.cancelarReserva(reserva({ estado: 'CANCELADA' })))
    expect(e.code).toBe('TRANSICION_INVALIDA')
  })
  it('cancela una SOLICITADA con su motivo', async () => {
    const r = await uc.cancelarReserva(reserva(), 'Cambio de planes')
    expect(gateway.cancelarReserva).toHaveBeenCalledWith('r1', 'Cambio de planes')
    expect(r.reserva.estado).toBe('CANCELADA')
  })
})

describe('listarMisReservas (UC13)', () => {
  it('guarda la copia solo de la primera página sin filtro', async () => {
    await uc.listarMisReservas()
    expect(cache.write).toHaveBeenCalledTimes(1)
    expect(cache.write.mock.calls[0][0]).toMatchObject({ total: 1, at: AHORA.getTime() })
    await uc.listarMisReservas({ estado: 'CONFIRMADA' })
    await uc.listarMisReservas({ pagina: 2 })
    expect(cache.write).toHaveBeenCalledTimes(1)
  })

  it('devuelve los datos en vivo cuando hay conexión', async () => {
    expect(await uc.listarMisReservas()).toMatchObject({ origen: 'en-vivo', copiaDe: null, total: 1 })
  })

  it('sin conexión devuelve la última copia, filtrada por estado', async () => {
    gateway.misReservas.mockRejectedValue(new BookingError('SIN_CONEXION', 'No hay conexión.'))
    cache.read.mockResolvedValue({ at: 123, total: 2, items: [reserva({ id: 'a' }), reserva({ id: 'b', estado: 'CONFIRMADA' })] })
    const todo = await uc.listarMisReservas()
    expect(todo).toMatchObject({ origen: 'copia', copiaDe: 123, total: 2 })
    const soloConfirmadas = await uc.listarMisReservas({ estado: 'CONFIRMADA' })
    expect(soloConfirmadas.items.map((r) => r.id)).toEqual(['b'])
  })

  it('sin conexión y sin copia propaga el error', async () => {
    gateway.misReservas.mockRejectedValue(new BookingError('SIN_CONEXION', 'No hay conexión.'))
    expect((await falla(uc.listarMisReservas())).code).toBe('SIN_CONEXION')
  })

  it('otros errores no se tapan con la copia', async () => {
    gateway.misReservas.mockRejectedValue(new BookingError('NO_AUTENTICADO', 'Sesión vencida', { status: 401 }))
    cache.read.mockResolvedValue({ at: 1, total: 1, items: [reserva()] })
    expect((await falla(uc.listarMisReservas())).code).toBe('NO_AUTENTICADO')
  })

  it('un fallo al guardar la copia no rompe la lectura', async () => {
    cache.write.mockRejectedValue(new Error('IndexedDB lleno'))
    expect((await uc.listarMisReservas()).origen).toBe('en-vivo')
  })
})
