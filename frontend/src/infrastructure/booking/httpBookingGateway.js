import { BookingError } from '../../domain/booking/errors.js'

/**
 * Adaptador HTTP del puerto BookingGateway: habla con el booking-service a través del Gateway
 * (Traefik), siguiendo contracts/openapi/booking.yaml (reservas del turista y panel del prestador: implementa los puertos
 * BookingGateway y ProviderGateway). Todas sus rutas exigen sesión: `fetchFn` debe ser el fetch
 * autenticado (infrastructure/auth/authorizedFetch), que pone el Bearer y renueva el token.
 */
/**
 * El booking-service real serializa `tarifa_dia` como TEXTO ("100000.00": es un decimal), aunque booking.yaml dice number.
 * Se convierte aquí para que el resto de la aplicación siempre reciba un número (o null si el día usa la tarifa base).
 */
const aNumero = (v) => (v == null || v === '' ? null : Number(v))
const dia = (d) => (d && typeof d === 'object' && 'tarifa_dia' in d ? { ...d, tarifa_dia: aNumero(d.tarifa_dia) } : d)
const dias = (r) => (Array.isArray(r?.dias) ? { ...r, dias: r.dias.map(dia) } : r)

export function createHttpBookingGateway({ baseUrl = '/api/bookings', fetchFn = (...a) => fetch(...a) } = {}) {
  async function http(method, path, { body, headers = {}, query } = {}) {
    const qs = query ? '?' + new URLSearchParams(Object.entries(query).filter(([, v]) => v != null && v !== '')) : ''
    // un encabezado sin valor (p. ej. sin Idempotency-Key) no se envía: fetch lo mandaría como el texto "undefined"
    const h = { Accept: 'application/json', ...Object.fromEntries(Object.entries(headers).filter(([, v]) => v != null)) }
    if (body) h['Content-Type'] = 'application/json'
    let res
    try { res = await fetchFn(`${baseUrl}${path}${qs}`, { method, headers: h, body: body ? JSON.stringify(body) : undefined }) }
    catch { throw new BookingError('SIN_CONEXION', 'No hay conexión con el servidor.') }
    const data = await res.json().catch(() => null)
    if (!res.ok)
      throw new BookingError(data?.error ?? (res.status === 401 ? 'NO_AUTENTICADO' : 'ERROR'), data?.message ?? res.statusText, {
        status: res.status, correlationId: data?.correlation_id, data: data?.actual ? { ...data, actual: dia(data.actual) } : data,
      })
    return { data, etag: res.headers.get('ETag'), status: res.status }
  }

  // Las operaciones sobre una reserva devuelven { data, etag }; el estado HTTP solo lo necesita guardarDiaCalendario
  const conEtag = (p) => p.then(({ data, etag }) => ({ data, etag }))

  return {
    consultarDisponibilidad: (servicioId, desde, hasta) =>
      http('GET', '/disponibilidad', { query: { servicio_id: servicioId, desde, hasta } }).then((r) => dias(r.data)),
    solicitarReserva: (body, idempotencyKey) => conEtag(http('POST', '/', { body, headers: { 'Idempotency-Key': idempotencyKey } })),
    misReservas: (params = {}) => http('GET', '/mis-reservas', { query: params }).then((r) => r.data),
    modificarReserva: (id, version, cambios) => conEtag(http('PATCH', `/${id}`, { body: cambios, headers: { 'If-Match': `"${version}"` } })),
    cancelarReserva: (id, motivo) => conEtag(http('POST', `/${id}/cancelar`, { body: motivo ? { motivo } : {} })),

    /* ---- Panel del prestador (UC19, UC20) ---- */
    solicitudesPrestador: (params = {}) => http('GET', '/prestador/solicitudes', { query: params }).then((r) => r.data),
    confirmarReserva: (id) => conEtag(http('POST', `/${id}/confirmar`)),
    rechazarReserva: (id, motivo) => conEtag(http('POST', `/${id}/rechazar`, { body: { motivo } })),
    calendarioServicio: (servicioId, desde, hasta) =>
      http('GET', `/prestador/calendario/${encodeURIComponent(servicioId)}`, { query: { desde, hasta } }).then((r) => dias(r.data)),
    abrirRangoCalendario: (servicioId, body, idempotencyKey) =>
      http('POST', `/prestador/calendario/${encodeURIComponent(servicioId)}/rango`, { body, headers: { 'Idempotency-Key': idempotencyKey } }).then((r) => r.data),
    // Sin If-Match solo crea el día (201); con If-Match edita si la versión coincide (200)
    guardarDiaCalendario: (servicioId, fecha, body, { version = null, idempotencyKey } = {}) =>
      http('PUT', `/prestador/calendario/${encodeURIComponent(servicioId)}/${encodeURIComponent(fecha)}`, {
        body, headers: { 'Idempotency-Key': idempotencyKey, ...(version != null ? { 'If-Match': `"${version}"` } : {}) },
      }).then((r) => ({ data: dia(r.data), etag: r.etag, creado: r.status === 201 })),
  }
}
