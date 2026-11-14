/*
 * PUERTOS (lo que la aplicación necesita del exterior). La aplicación solo conoce estas interfaces;
 * los adaptadores de infrastructure/ las implementan.
 *
 * BookingGateway  (puerto de salida, nombres = operationId de contracts/openapi/booking.yaml)
 *   consultarDisponibilidad(servicioId, desde, hasta) -> { servicio_id, dias: DiaDisponible[] }
 *   solicitarReserva(body, idempotencyKey)            -> { data: Reserva, etag }
 *   misReservas({ estado, pagina, tamano })           -> { items, pagina, tamano, total }
 *   modificarReserva(id, version, cambios)            -> { data: Reserva, etag }
 *   cancelarReserva(id, motivo)                       -> { data: Reserva, etag }
 *   Los errores se lanzan como BookingError (domain/booking/errors.js).
 *
 * Session  (puerto de salida)           isAuthenticated() -> boolean
 * BookingCache (puerto de salida)       read() -> { items, total, at } | null   ·   write({ items, total, at })
 * Clock (puerto de salida)              now() -> Date
 */
export const BOOKING_GATEWAY_METHODS = Object.freeze([
  'consultarDisponibilidad',
  'solicitarReserva',
  'misReservas',
  'modificarReserva',
  'cancelarReserva',
])

/** Falla pronto y con un mensaje claro si un adaptador no implementa el puerto completo. */
export function assertBookingGateway(gateway) {
  const faltan = BOOKING_GATEWAY_METHODS.filter((m) => typeof gateway?.[m] !== 'function')
  if (faltan.length) throw new TypeError(`El adaptador de reservas no implementa el puerto BookingGateway: faltan ${faltan.join(', ')}`)
  return gateway
}
