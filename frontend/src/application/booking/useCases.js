import { BookingError, CODIGOS } from '../../domain/booking/errors.js'
import { today, tomorrow } from '../../domain/booking/dates.js'
import { decisionCancelar, decisionModificar, validarSolicitud, ventanaReserva } from '../../domain/booking/rules.js'
import { assertBookingGateway } from './ports.js'

/*
 * Casos de uso de reservas (UC10–UC13). Orquestan el dominio y los puertos; no saben de Vue,
 * de HTTP ni de IndexedDB. Se construyen con sus dependencias inyectadas (ver composition.js).
 *
 * Las reglas se comprueban aquí ANTES de llamar al backend: ahorran una petición y dan el mismo
 * mensaje que daría el servidor. El servidor sigue siendo la autoridad (puede responder 409).
 */
export function createBookingUseCases({ gateway, session, cache, clock }) {
  assertBookingGateway(gateway)
  const ahora = () => clock.now()

  const rechazar = (decision) => {
    throw new BookingError(decision.codigo, decision.mensaje, { status: 409 })
  }

  return {
    hoy: () => today(ahora()),
    manana: () => tomorrow(ahora()),
    ventana: () => ventanaReserva(ahora()),

    /** UC10 · pública */
    async consultarDisponibilidad(servicioId, ventana = ventanaReserva(ahora())) {
      const r = await gateway.consultarDisponibilidad(servicioId, ventana.desde, ventana.hasta)
      return { ...r, ...ventana }
    },

    /** UC11 · requiere sesión y conexión; `idempotencyKey` identifica el intento de envío */
    async solicitarReserva({ servicioId, fecha, personas, maxPersonas, idempotencyKey }) {
      if (!session.isAuthenticated()) throw new BookingError(CODIGOS.NO_AUTENTICADO, 'Inicia sesión para solicitar una reserva.', { status: 401 })
      const errores = validarSolicitud({ fecha, personas }, { ahora: ahora(), maxPersonas })
      if (errores.length) throw new BookingError(CODIGOS.VALIDACION, errores[0], { status: 400 })
      const { data, etag } = await gateway.solicitarReserva({ servicio_id: servicioId, fecha_reserva: fecha, numero_personas: personas }, idempotencyKey)
      return { reserva: data, etag }
    },

    /** UC13 · si no hay conexión devuelve la última copia guardada (solo lectura) */
    async listarMisReservas({ estado, pagina = 1, tamano = 20 } = {}) {
      try {
        const res = await gateway.misReservas({ estado, pagina, tamano })
        // La copia local es un extra: se guarda sin esperar para que nunca retrase ni rompa la lectura
        if (!estado && pagina === 1) Promise.resolve(cache.write({ items: res.items, total: res.total, at: ahora().getTime() })).catch(() => {})
        return { ...res, origen: 'en-vivo', copiaDe: null }
      } catch (e) {
        if (!(e instanceof BookingError) || e.code !== CODIGOS.SIN_CONEXION) throw e
        const guardada = await cache.read().catch(() => null)
        if (!guardada) throw e
        const items = estado ? guardada.items.filter((r) => r.estado === estado) : guardada.items
        return { items, pagina: 1, tamano, total: items.length, origen: 'copia', copiaDe: guardada.at }
      }
    },

    /** UC12 · solo SOLICITADA; usa la versión que el usuario vio (If-Match) */
    async modificarReserva(reserva, cambios) {
      const decision = decisionModificar(reserva)
      if (!decision.permitido) rechazar(decision)
      const fecha = cambios.fecha_reserva ?? reserva.fecha_reserva
      const personas = cambios.numero_personas ?? reserva.numero_personas
      const errores = validarSolicitud({ fecha, personas }, { ahora: ahora() })
      if (errores.length) throw new BookingError(CODIGOS.VALIDACION, errores[0], { status: 400 })
      const { data, etag } = await gateway.modificarReserva(reserva.id, reserva.version, cambios)
      return { reserva: data, etag }
    },

    /** UC12 · SOLICITADA siempre; CONFIRMADA hasta el día anterior */
    async cancelarReserva(reserva, motivo) {
      const decision = decisionCancelar(reserva, today(ahora()))
      if (!decision.permitido) rechazar(decision)
      const { data, etag } = await gateway.cancelarReserva(reserva.id, motivo)
      return { reserva: data, etag }
    },
  }
}
