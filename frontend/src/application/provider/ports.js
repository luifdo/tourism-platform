/*
 * PUERTO del panel del prestador (UC19 calendario, UC20 solicitudes). Los nombres son los operationId de
 * contracts/openapi/booking.yaml. El adaptador HTTP de reservas implementa este puerto además del BookingGateway.
 *
 * ProviderGateway  (puerto de salida)
 *   solicitudesPrestador({ estado, servicio_id, desde, hasta, pagina, tamano }) -> { items: Reserva[], pagina, tamano, total }
 *   confirmarReserva(id)                       -> { data: Reserva, etag }
 *   rechazarReserva(id, motivo)                -> { data: Reserva, etag }
 *   calendarioServicio(servicioId, desde, hasta) -> { servicio_id, dias: DiaCalendario[] }
 *   abrirRangoCalendario(servicioId, body, idempotencyKey) -> { creados: fecha[], omitidos: fecha[] }
 *       body: { desde, hasta, dias_semana?, cupos_totales, tarifa_dia? }
 *   guardarDiaCalendario(servicioId, fecha, body, { version, idempotencyKey }) -> { data: DiaCalendario, etag, creado: boolean }
 *       body: { cupos_totales, tarifa_dia? }. Sin `version` solo crea el día (409 DIA_EXISTENTE si ya existe); con `version`
 *       lo edita (409 VERSION_DISTINTA con { version_actual, actual } en BookingError.data si cambió en el servidor).
 *   DiaCalendario: { fecha, cupos_totales, cupos_disponibles, cupos_reservados, tarifa_dia|null, version }
 *   Los errores se lanzan como BookingError (domain/booking/errors.js).
 *
 * Session (puerto de salida)  isAuthenticated() -> boolean
 * Clock   (puerto de salida)  now() -> Date
 */
export const PROVIDER_GATEWAY_METHODS = Object.freeze([
  'solicitudesPrestador', 'confirmarReserva', 'rechazarReserva', 'calendarioServicio', 'abrirRangoCalendario', 'guardarDiaCalendario',
])

export function assertProviderGateway(gateway) {
  const faltan = PROVIDER_GATEWAY_METHODS.filter((m) => typeof gateway?.[m] !== 'function')
  if (faltan.length) throw new TypeError(`El adaptador del prestador no implementa el puerto ProviderGateway: faltan ${faltan.join(', ')}`)
  return gateway
}
