import { BookingError } from '../../domain/booking/errors.js'

/**
 * Adaptador HTTP del puerto BookingGateway: habla con el booking-service a través del Gateway
 * (Traefik), siguiendo contracts/openapi/booking.yaml.
 */
export function createHttpBookingGateway({ baseUrl = '/api/bookings', getToken = () => null, fetchFn = (...a) => fetch(...a) } = {}) {
  async function http(method, path, { body, headers = {}, query } = {}) {
    const qs = query ? '?' + new URLSearchParams(Object.entries(query).filter(([, v]) => v != null && v !== '')) : ''
    const h = { Accept: 'application/json', ...headers }
    if (body) h['Content-Type'] = 'application/json'
    const token = getToken()
    if (token) h.Authorization = `Bearer ${token}`
    let res
    try { res = await fetchFn(`${baseUrl}${path}${qs}`, { method, headers: h, body: body ? JSON.stringify(body) : undefined }) }
    catch { throw new BookingError('SIN_CONEXION', 'No hay conexión con el servidor.') }
    const data = await res.json().catch(() => null)
    if (!res.ok)
      throw new BookingError(data?.error ?? (res.status === 401 ? 'NO_AUTENTICADO' : 'ERROR'), data?.message ?? res.statusText, { status: res.status, correlationId: data?.correlation_id })
    return { data, etag: res.headers.get('ETag') }
  }

  return {
    consultarDisponibilidad: (servicioId, desde, hasta) =>
      http('GET', '/disponibilidad', { query: { servicio_id: servicioId, desde, hasta } }).then((r) => r.data),
    solicitarReserva: (body, idempotencyKey) => http('POST', '/', { body, headers: { 'Idempotency-Key': idempotencyKey } }),
    misReservas: (params = {}) => http('GET', '/mis-reservas', { query: params }).then((r) => r.data),
    modificarReserva: (id, version, cambios) => http('PATCH', `/${id}`, { body: cambios, headers: { 'If-Match': `"${version}"` } }),
    cancelarReserva: (id, motivo) => http('POST', `/${id}/cancelar`, { body: motivo ? { motivo } : {} }),
  }
}
