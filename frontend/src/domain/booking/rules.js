import { addDays, startOfDay, today, tomorrow } from './dates.js'
import { CODIGOS } from './errors.js'

/*
 * Reglas de negocio de las reservas (booking.yaml + Guía Técnica del Módulo 3).
 * Todo son funciones puras sobre datos planos: sin Vue, sin red, sin almacenamiento.
 */

export const ESTADOS = Object.freeze(['SOLICITADA', 'CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'FINALIZADA'])
/** Estados que ocupan cupos */
export const ACTIVOS = Object.freeze(['SOLICITADA', 'CONFIRMADA'])
export const PLAZO_RESPUESTA_HORAS = 48
/** El contrato limita la consulta de disponibilidad a 62 días */
export const MAX_DIAS_CONSULTA = 62

/** Rango reservable: desde mañana y 62 días (el día de "mañana" cuenta). */
export function ventanaReserva(ahora = new Date()) {
  const desde = tomorrow(ahora)
  return { desde, hasta: addDays(desde, MAX_DIAS_CONSULTA - 1) }
}

/** Plazo del prestador para responder: mín(ahora + 48 h, 00:00 del día de la reserva). */
export function plazoRespuesta(fechaReserva, ahora = new Date()) {
  const limite = startOfDay(fechaReserva).getTime()
  return new Date(Math.min(ahora.getTime() + PLAZO_RESPUESTA_HORAS * 3600e3, limite)).toISOString()
}

/** Valida una solicitud. Devuelve la lista de problemas (vacía si es válida). */
export function validarSolicitud({ fecha, personas }, { ahora = new Date(), maxPersonas } = {}) {
  const errores = []
  if (!fecha || fecha < tomorrow(ahora)) errores.push('La fecha debe ser a partir de mañana.')
  if (!Number.isInteger(personas) || personas < 1) errores.push('El número de personas debe ser al menos 1.')
  else if (maxPersonas != null && personas > maxPersonas) errores.push(`Solo hay ${maxPersonas} cupos para ese día.`)
  return errores
}

const permitir = () => ({ permitido: true })
const negar = (codigo, mensaje) => ({ permitido: false, codigo, mensaje })

/** UC12: solo se modifica una reserva SOLICITADA. */
export function decisionModificar(reserva) {
  return reserva.estado === 'SOLICITADA'
    ? permitir()
    : negar(CODIGOS.TRANSICION_INVALIDA, `Solo se puede modificar en estado SOLICITADA; está ${reserva.estado}.`)
}

/**
 * UC12: el turista cancela SOLICITADA siempre y CONFIRMADA hasta las 23:59 del día anterior.
 * Estados finales (RECHAZADA, CANCELADA, FINALIZADA) no admiten cancelar.
 */
export function decisionCancelar(reserva, hoy) {
  if (!ACTIVOS.includes(reserva.estado)) return negar(CODIGOS.TRANSICION_INVALIDA, `No se puede cancelar una reserva ${reserva.estado}.`)
  if (reserva.estado === 'CONFIRMADA' && reserva.fecha_reserva <= hoy)
    return negar(CODIGOS.FUERA_DE_PLAZO, 'Solo se puede cancelar hasta las 23:59 del día anterior a la reserva.')
  return permitir()
}

/** Transiciones del sistema: plazo vencido -> RECHAZADA; fecha pasada -> FINALIZADA. Devuelve la misma referencia si nada cambia. */
export function liquidar(reserva, ahora = new Date()) {
  if (reserva.estado === 'SOLICITADA' && reserva.expira_en && new Date(reserva.expira_en) < ahora)
    return { ...reserva, estado: 'RECHAZADA', expira_en: null, motivo: 'Venció el plazo de respuesta del prestador.', version: reserva.version + 1 }
  if (reserva.estado === 'CONFIRMADA' && reserva.fecha_reserva < today(ahora))
    return { ...reserva, estado: 'FINALIZADA', version: reserva.version + 1 }
  return reserva
}

/** Cupos ocupados por reservas activas de un servicio en una fecha (opcionalmente sin contar una reserva). */
export function cuposReservados(reservas, servicioId, fecha, excluirId) {
  return reservas
    .filter((r) => r.servicio_id === servicioId && r.fecha_reserva === fecha && ACTIVOS.includes(r.estado) && r.id !== excluirId)
    .reduce((suma, r) => suma + r.numero_personas, 0)
}

export const cuposDisponibles = (total, reservados) => Math.max(0, total - reservados)

/** Un turista no puede tener dos reservas activas para el mismo servicio y fecha. */
export function esDuplicada(reservas, { turistaId, servicioId, fecha }, excluirId) {
  return reservas.some(
    (r) => r.turista_id === turistaId && r.servicio_id === servicioId && r.fecha_reserva === fecha && ACTIVOS.includes(r.estado) && r.id !== excluirId,
  )
}

/** Tarifa por persona de un día: la del día si existe, si no la tarifa base del catálogo. */
export const tarifaDia = (dia, tarifaBase) => dia?.tarifa_dia ?? tarifaBase

/** Máximo de personas que se pueden solicitar para un día. */
export const maxPersonas = (dia) => dia?.cupos_disponibles ?? 1

export const estimado = (tarifa, personas) => tarifa * personas

/** Estado de un día del calendario: 'fuera' | 'cerrado' | 'agotado' | 'ok' */
export function estadoDia(fecha, info, { desde, hasta }) {
  if (fecha < desde || fecha > hasta) return 'fuera'
  if (!info) return 'cerrado'
  return info.cupos_disponibles === 0 ? 'agotado' : 'ok'
}

/** Línea de tiempo: Solicitada → (Confirmada | Rechazada | Cancelada) → Finalizada */
export function lineaDeTiempo(reserva) {
  const medio = reserva.estado === 'RECHAZADA' || reserva.estado === 'CANCELADA' ? reserva.estado : 'CONFIRMADA'
  const alcanzado = { SOLICITADA: 0, CONFIRMADA: 1, RECHAZADA: 1, CANCELADA: 1, FINALIZADA: 2 }[reserva.estado]
  return ['SOLICITADA', medio, 'FINALIZADA'].map((estado, i) => ({ estado, alcanzado: i <= alcanzado, negativo: i === 1 && medio !== 'CONFIRMADA' }))
}
