import { describe, expect, it, vi } from 'vitest'
import { createHttpBookingGateway } from '../../src/infrastructure/booking/httpBookingGateway.js'
import { assertProviderGateway } from '../../src/application/provider/ports.js'
import { assertBookingGateway } from '../../src/application/booking/ports.js'
import { BookingError } from '../../src/domain/booking/errors.js'

/* El mismo adaptador de reservas implementa el puerto del prestador: aquí se fijan sus rutas y encabezados (booking.yaml). */
const respuesta = (cuerpo, { status = 200, etag } = {}) => ({
  ok: status < 400, status, statusText: 'x',
  json: async () => { if (cuerpo === undefined) throw new SyntaxError('no es JSON'); return cuerpo },
  headers: { get: (h) => (h.toLowerCase() === 'etag' ? etag ?? null : null) },
})
const crear = (fetchFn) => createHttpBookingGateway({ baseUrl: '/api/bookings', fetchFn })
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }
const dia = { fecha: '2026-11-20', cupos_totales: 10, cupos_disponibles: 10, cupos_reservados: 0, tarifa_dia: null, version: 1 }

describe('adaptador HTTP de reservas: panel del prestador', () => {
  it('implementa el puerto del prestador además del de reservas', () => {
    const gw = crear(vi.fn())
    expect(assertProviderGateway(gw)).toBeTruthy()
    expect(assertBookingGateway(gw)).toBeTruthy()
  })

  it('solicitudes: GET /prestador/solicitudes con los filtros del contrato', async () => {
    const fetchFn = vi.fn(async () => respuesta({ items: [], pagina: 1, tamano: 20, total: 0 }))
    await crear(fetchFn).solicitudesPrestador({ estado: 'SOLICITADA', servicio_id: 's1', desde: '2026-11-01', hasta: undefined, pagina: 2, tamano: 20 })
    const [url, init] = fetchFn.mock.calls[0]
    const u = new URL(url, 'http://x')
    expect(u.pathname).toBe('/api/bookings/prestador/solicitudes')
    expect(Object.fromEntries(u.searchParams)).toEqual({ estado: 'SOLICITADA', servicio_id: 's1', desde: '2026-11-01', pagina: '2', tamano: '20' })
    expect(init.method).toBe('GET')
  })

  it('confirmar: POST /{id}/confirmar y devuelve la reserva con su ETag', async () => {
    const fetchFn = vi.fn(async () => respuesta({ id: 'r1', estado: 'CONFIRMADA' }, { etag: '"2"' }))
    const r = await crear(fetchFn).confirmarReserva('r1')
    expect(fetchFn.mock.calls[0][0]).toBe('/api/bookings/r1/confirmar')
    expect(fetchFn.mock.calls[0][1].method).toBe('POST')
    expect(r).toEqual({ data: { id: 'r1', estado: 'CONFIRMADA' }, etag: '"2"' }) // sin el estado HTTP
  })

  it('rechazar: POST /{id}/rechazar con el motivo en el cuerpo', async () => {
    const fetchFn = vi.fn(async () => respuesta({ id: 'r1', estado: 'RECHAZADA' }, { etag: '"2"' }))
    await crear(fetchFn).rechazarReserva('r1', 'Sendero cerrado')
    expect(fetchFn.mock.calls[0][0]).toBe('/api/bookings/r1/rechazar')
    expect(JSON.parse(fetchFn.mock.calls[0][1].body)).toEqual({ motivo: 'Sendero cerrado' })
  })

  it('calendario: GET /prestador/calendario/{servicio}?desde&hasta', async () => {
    const fetchFn = vi.fn(async () => respuesta({ servicio_id: 's1', dias: [dia] }))
    const r = await crear(fetchFn).calendarioServicio('s1', '2026-11-13', '2026-12-12')
    expect(fetchFn.mock.calls[0][0]).toBe('/api/bookings/prestador/calendario/s1?desde=2026-11-13&hasta=2026-12-12')
    expect(r.dias).toHaveLength(1)
  })

  it('abrir rango: POST .../rango con la Idempotency-Key', async () => {
    const fetchFn = vi.fn(async () => respuesta({ creados: ['2026-11-20'], omitidos: [] }, { status: 201 }))
    const r = await crear(fetchFn).abrirRangoCalendario('s1', { desde: '2026-11-13', hasta: '2026-11-20', cupos_totales: 8 }, 'clave-1')
    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('/api/bookings/prestador/calendario/s1/rango')
    expect(init.method).toBe('POST')
    expect(init.headers['Idempotency-Key']).toBe('clave-1')
    expect(r).toEqual({ creados: ['2026-11-20'], omitidos: [] })
  })

  describe('guardar un día', () => {
    it('sin versión: PUT sin If-Match (solo crea) y el 201 se informa como creado', async () => {
      const fetchFn = vi.fn(async () => respuesta(dia, { status: 201, etag: '"1"' }))
      const r = await crear(fetchFn).guardarDiaCalendario('s1', '2026-11-20', { cupos_totales: 10, tarifa_dia: null }, { idempotencyKey: 'k' })
      const [url, init] = fetchFn.mock.calls[0]
      expect(url).toBe('/api/bookings/prestador/calendario/s1/2026-11-20')
      expect(init.method).toBe('PUT')
      expect(init.headers['If-Match']).toBeUndefined()
      expect(init.headers['Idempotency-Key']).toBe('k')
      expect(r).toEqual({ data: dia, etag: '"1"', creado: true })
    })

    it('con versión: manda If-Match con el ETag entre comillas y el 200 es una edición', async () => {
      const fetchFn = vi.fn(async () => respuesta({ ...dia, version: 4 }, { status: 200, etag: '"4"' }))
      const r = await crear(fetchFn).guardarDiaCalendario('s1', '2026-11-20', { cupos_totales: 6 }, { version: 3, idempotencyKey: 'k' })
      expect(fetchFn.mock.calls[0][1].headers['If-Match']).toBe('"3"')
      expect(r.creado).toBe(false)
    })

    it('sin Idempotency-Key no manda el encabezado (no el texto "undefined")', async () => {
      const fetchFn = vi.fn(async () => respuesta(dia, { status: 201, etag: '"1"' }))
      await crear(fetchFn).guardarDiaCalendario('s1', '2026-11-20', { cupos_totales: 10 }, {})
      expect(Object.keys(fetchFn.mock.calls[0][1].headers)).not.toContain('Idempotency-Key')
    })

    it('escapa la fecha y el servicio en la ruta', async () => {
      const fetchFn = vi.fn(async () => respuesta(dia, { status: 201 }))
      await crear(fetchFn).guardarDiaCalendario('a/b', '2026-11-20/../x', { cupos_totales: 1 }, {})
      expect(fetchFn.mock.calls[0][0]).toBe('/api/bookings/prestador/calendario/a%2Fb/2026-11-20%2F..%2Fx')
    })
  })

  describe('errores', () => {
    it('el 409 VERSION_DISTINTA conserva `version_actual` y `actual` en `data` (INTEGRACION.md §2.2)', async () => {
      const actual = { ...dia, cupos_totales: 4, version: 5 }
      const e = await falla(crear(async () => respuesta({ error: 'VERSION_DISTINTA', message: 'cambió', correlation_id: 'c-1', version_actual: 5, actual }, { status: 409 })).guardarDiaCalendario('s1', '2026-11-20', { cupos_totales: 6 }, { version: 2 }))
      expect(e).toBeInstanceOf(BookingError)
      expect(e).toMatchObject({ code: 'VERSION_DISTINTA', status: 409, correlationId: 'c-1', data: { version_actual: 5, actual } })
    })

    it.each([
      [409, 'PETICION_EN_PROCESO'], [503, 'IDEMPOTENCIA_NO_DISPONIBLE'], [409, 'DIA_EXISTENTE'], [409, 'CUPOS_COMPROMETIDOS'],
      [422, 'SUPERA_AFORO'], [409, 'PLAZO_VENCIDO'], [403, 'ROL_NO_PERMITIDO'],
    ])('el %i %s del contrato llega con su código', async (status, code) => {
      const e = await falla(crear(async () => respuesta({ error: code, message: 'texto', correlation_id: 'c' }, { status })).confirmarReserva('r1'))
      expect(e).toMatchObject({ code, status })
    })

    it('el 401 sin cuerpo es NO_AUTENTICADO y sin red es SIN_CONEXION', async () => {
      expect((await falla(crear(async () => respuesta(undefined, { status: 401 })).solicitudesPrestador())).code).toBe('NO_AUTENTICADO')
      expect((await falla(crear(async () => { throw new TypeError('Failed to fetch') }).solicitudesPrestador())).code).toBe('SIN_CONEXION')
    })
  })
})
