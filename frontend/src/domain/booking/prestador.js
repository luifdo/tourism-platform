import { addDays, tomorrow, today, weekday } from './dates.js'
import { CODIGOS } from './errors.js'

/*
 * Reglas del panel del prestador (UC19 calendario, UC20 solicitudes), según booking.yaml. Funciones puras:
 * sin Vue, sin red, sin almacenamiento. El servidor sigue siendo la autoridad: estas comprobaciones ahorran una
 * petición y dan el mismo mensaje que daría él.
 */
export const MOTIVO_MIN = 3
export const MOTIVO_MAX = 500
/** El contrato limita un rango a 366 días después de `desde`. */
export const MAX_DIAS_RANGO = 366
/** Faltando menos de esto para `expira_en`, la solicitud se marca como urgente. */
export const HORAS_URGENTE = 6
export const DIAS_SEMANA = Object.freeze([1, 2, 3, 4, 5, 6, 7]) // 1 = lunes … 7 = domingo

const largo = (t) => [...t].length

/** El rechazo exige un motivo de 3 a 500 caracteres (contrato: MotivoObligatorio). */
export function validarMotivo(texto) {
  const motivo = String(texto ?? '').trim()
  if (largo(motivo) < MOTIVO_MIN) return { ok: false, codigo: CODIGOS.MOTIVO_INVALIDO, motivo }
  if (largo(motivo) > MOTIVO_MAX) return { ok: false, codigo: CODIGOS.MOTIVO_INVALIDO, motivo }
  return { ok: true, motivo }
}

const permitir = () => ({ permitido: true })
const negar = (codigo, mensaje) => ({ permitido: false, codigo, mensaje })

/** UC20: solo el prestador dueño, en SOLICITADA y antes de `expira_en`. */
export function decisionConfirmar(reserva, ahora = new Date()) {
  if (reserva.estado !== 'SOLICITADA') return negar(CODIGOS.TRANSICION_INVALIDA, `Solo se puede confirmar una solicitud SOLICITADA; está ${reserva.estado}.`)
  if (reserva.expira_en && new Date(reserva.expira_en) <= ahora) return negar(CODIGOS.PLAZO_VENCIDO, 'El plazo para responder esta solicitud ya venció.')
  return permitir()
}

/** UC20: rechazar solo en SOLICITADA (libera los cupos). */
export function decisionRechazar(reserva) {
  return reserva.estado === 'SOLICITADA'
    ? permitir()
    : negar(CODIGOS.TRANSICION_INVALIDA, `Solo se puede rechazar una solicitud SOLICITADA; está ${reserva.estado}.`)
}

/** Horas que faltan para que venza el plazo de respuesta, o null si no aplica. */
export function horasRestantes(reserva, ahora = new Date()) {
  if (reserva.estado !== 'SOLICITADA' || !reserva.expira_en) return null
  return (new Date(reserva.expira_en).getTime() - ahora.getTime()) / 3600e3
}

/** 'vencida' | 'urgente' | 'normal' | null (las que ya no esperan respuesta). Sirve para destacar lo que no puede esperar. */
export function urgencia(reserva, ahora = new Date()) {
  const h = horasRestantes(reserva, ahora)
  if (h == null) return null
  return h <= 0 ? 'vencida' : h <= HORAS_URGENTE ? 'urgente' : 'normal'
}

/** Más urgente primero (la API ya las trae por `expira_en`; se usa al mezclar páginas o al recalcular). */
export const porUrgencia = (a, b) => (a.expira_en ?? '9999').localeCompare(b.expira_en ?? '9999')

const entero = (v) => Number.isInteger(v)
const tarifaValida = (t) => t == null || (typeof t === 'number' && Number.isFinite(t) && t >= 0)

/** Cuántos días se abrirían con ese rango y esos días de la semana (para mostrarlo antes de enviar). */
export function diasDelRango({ desde, hasta, diasSemana }) {
  if (!desde || !hasta || hasta < desde) return []
  const dias = []
  const filtro = diasSemana?.length ? new Set(diasSemana) : null
  for (let f = desde, i = 0; f <= hasta && i <= MAX_DIAS_RANGO + 1; f = addDays(f, 1), i++) if (!filtro || filtro.has(weekday(f))) dias.push(f)
  return dias
}

/**
 * UC19 · abrir un rango de días. Devuelve los problemas como [{ campo, codigo }] (vacía si es válido).
 * `aforo`: capacidad de carga oficial del servicio, si se conoce (el servidor responde SUPERA_AFORO si no).
 */
export function validarRango({ desde, hasta, diasSemana, cuposTotales, tarifaDia }, { ahora = new Date(), aforo } = {}) {
  const errores = []
  const e = (campo, codigo) => errores.push({ campo, codigo })
  if (!desde) e('desde', 'FECHA_REQUERIDA')
  else if (desde < today(ahora)) e('desde', 'FECHA_PASADA')
  if (!hasta) e('hasta', 'FECHA_REQUERIDA')
  else if (desde && hasta < desde) e('hasta', 'RANGO_INVERTIDO')
  else if (desde && hasta > addDays(desde, MAX_DIAS_RANGO)) e('hasta', 'RANGO_MUY_LARGO')
  if (diasSemana && (!Array.isArray(diasSemana) || diasSemana.some((d) => !DIAS_SEMANA.includes(d)) || new Set(diasSemana).size !== diasSemana.length)) e('diasSemana', 'DIAS_INVALIDOS')
  else if (desde && hasta && !errores.some((x) => x.campo === 'hasta' || x.campo === 'desde') && !diasDelRango({ desde, hasta, diasSemana }).length) e('diasSemana', 'RANGO_SIN_DIAS')
  if (!entero(cuposTotales) || cuposTotales < 1) e('cuposTotales', 'CUPOS_INVALIDOS')
  else if (aforo != null && cuposTotales > aforo) e('cuposTotales', CODIGOS.SUPERA_AFORO)
  if (!tarifaValida(tarifaDia)) e('tarifaDia', 'TARIFA_INVALIDA')
  return errores
}

/**
 * UC19 · crear o editar un día. No puede quedar por debajo de lo ya reservado ni por encima del aforo oficial.
 * Con 0 cupos el día queda cerrado (no se ofrece).
 */
export function validarDia({ cuposTotales, tarifaDia }, { reservados = 0, aforo } = {}) {
  const errores = []
  const e = (campo, codigo) => errores.push({ campo, codigo })
  if (!entero(cuposTotales) || cuposTotales < 0) e('cuposTotales', 'CUPOS_INVALIDOS')
  else if (cuposTotales < reservados) e('cuposTotales', CODIGOS.CUPOS_COMPROMETIDOS)
  else if (aforo != null && cuposTotales > aforo) e('cuposTotales', CODIGOS.SUPERA_AFORO)
  if (!tarifaValida(tarifaDia)) e('tarifaDia', 'TARIFA_INVALIDA')
  return errores
}

/** Ventana por defecto del calendario: de mañana a 30 días (el prestador puede ampliarla hasta 366). */
export function ventanaCalendario(ahora = new Date(), dias = 30) {
  const desde = tomorrow(ahora)
  return { desde, hasta: addDays(desde, dias - 1) }
}

/** Resumen de una lista de días: cuántos están abiertos, cerrados (0 cupos), y los cupos reservados y libres. */
export function resumenCalendario(dias) {
  return dias.reduce((r, d) => {
    if (d.cupos_totales === 0) r.cerrados += 1
    else r.abiertos += 1
    r.reservados += d.cupos_reservados
    r.disponibles += d.cupos_disponibles
    return r
  }, { abiertos: 0, cerrados: 0, reservados: 0, disponibles: 0 })
}
