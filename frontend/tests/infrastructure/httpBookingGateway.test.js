import { describe, expect, it, vi } from 'vitest'
import { createHttpBookingGateway } from '../../src/infrastructure/booking/httpBookingGateway.js'
import { assertBookingGateway } from '../../src/application/booking/ports.js'
import { BookingError } from '../../src/domain/booking/errors.js'

const respuesta = (cuerpo, { status = 200, etag } = {}) => ({
  ok: status < 400, status, statusText: 'x',
  json: async () => cuerpo,
  headers: { get: (h) => (h.toLowerCase() === 'etag' ? etag ?? null : null) },
})
const crear = (fetchFn, token = 'jwt-123') => createHttpBookingGateway({ baseUrl: '/api/bookings', getToken: () => token, fetchFn })
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }

describe('adaptador HTTP de reservas', () => {
  it('implementa el puerto BookingGateway completo', () => {
    expect(assertBookingGateway(crear(vi.fn()))).toBeTruthy()
  })

  it('consulta la disponibilidad con los parámetros del contrato', async () => {
    const fetchFn = vi.fn(async () => respuesta({ servicio_id: 's1', dias: [] }))
    await crear(fetchFn).consultarDisponibilidad('s1', '2026-10-27', '2026-11-05')
    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('/api/bookings/disponibilidad?servicio_id=s1&desde=2026-10-27&hasta=2026-11-05')
    expect(init.method).toBe('GET')
  })

  it('al solicitar envía la Idempotency-Key, el JWT y el cuerpo JSON, y devuelve el ETag', async () => {
    const fetchFn = vi.fn(async () => respuesta({ id: 'r1' }, { status: 201, etag: '"1"' }))
    const r = await crear(fetchFn).solicitarReserva({ servicio_id: 's1', fecha_reserva: '2026-11-05', numero_personas: 2 }, 'clave-1')
    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('/api/bookings/')
    expect(init.method).toBe('POST')
    expect(init.headers).toMatchObject({ 'Idempotency-Key': 'clave-1', Authorization: 'Bearer jwt-123', 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body)).toEqual({ servicio_id: 's1', fecha_reserva: '2026-11-05', numero_personas: 2 })
    expect(r).toEqual({ data: { id: 'r1' }, etag: '"1"' })
  })

  it('al modificar envía If-Match con la versión entre comillas', async () => {
    const fetchFn = vi.fn(async () => respuesta({ id: 'r1' }, { etag: '"4"' }))
    await crear(fetchFn).modificarReserva('r1', 3, { numero_personas: 4 })
    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('/api/bookings/r1')
    expect(init.method).toBe('PATCH')
    expect(init.headers['If-Match']).toBe('"3"')
  })

  it('al cancelar usa POST /{id}/cancelar con el motivo opcional', async () => {
    const fetchFn = vi.fn(async () => respuesta({ id: 'r1' }))
    await crear(fetchFn).cancelarReserva('r1', 'Cambio de planes')
    expect(fetchFn.mock.calls[0][0]).toBe('/api/bookings/r1/cancelar')
    expect(JSON.parse(fetchFn.mock.calls[0][1].body)).toEqual({ motivo: 'Cambio de planes' })
  })

  it('sin token no envía Authorization (las rutas públicas no lo necesitan)', async () => {
    const fetchFn = vi.fn(async () => respuesta({ servicio_id: 's1', dias: [] }))
    await crear(fetchFn, null).consultarDisponibilidad('s1', '2026-10-27', '2026-10-28')
    expect(fetchFn.mock.calls[0][1].headers.Authorization).toBeUndefined()
  })

  it('traduce el formato de error del contrato a BookingError', async () => {
    const fetchFn = vi.fn(async () => respuesta({ error: 'CUPOS_INSUFICIENTES', message: 'Solo quedan 1 cupos.', correlation_id: 'abc' }, { status: 409 }))
    const e = await falla(crear(fetchFn).solicitarReserva({}, 'k'))
    expect(e).toBeInstanceOf(BookingError)
    expect(e).toMatchObject({ code: 'CUPOS_INSUFICIENTES', status: 409, correlationId: 'abc', message: 'Solo quedan 1 cupos.' })
  })

  it('un 401 sin cuerpo es NO_AUTENTICADO', async () => {
    const fetchFn = vi.fn(async () => ({ ok: false, status: 401, statusText: 'Unauthorized', json: async () => { throw new Error('sin cuerpo') }, headers: { get: () => null } }))
    expect((await falla(crear(fetchFn).misReservas())).code).toBe('NO_AUTENTICADO')
  })

  it('un fallo de red es SIN_CONEXION', async () => {
    const e = await falla(crear(vi.fn(async () => { throw new TypeError('Failed to fetch') })).misReservas())
    expect(e).toMatchObject({ code: 'SIN_CONEXION', status: 0 })
  })
})
