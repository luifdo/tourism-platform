import { BookingError } from '../../domain/booking/errors.js'
import { addDays, tomorrow, today, weekday } from '../../domain/booking/dates.js'
import {
  MAX_DIAS_CONSULTA, cuposDisponibles, cuposReservados, decisionCancelar, decisionModificar,
  esDuplicada, liquidar, plazoRespuesta, validarSolicitud,
} from '../../domain/booking/rules.js'

/*
 * Adaptador SIMULADO del puerto BookingGateway: hace el papel del booking-service mientras no exista
 * el Gateway. Reutiliza las reglas del dominio y responde con los mismos códigos y encabezados
 * que el contrato, para que la UI y los casos de uso no noten la diferencia.
 *
 * `servicios`: { [id]: { fee, capacidad, cierra?: number[] (días de semana), recargo?: { dia, factor } } }
 */
const KEY = 'mock.bookings.v1'
const DEMO_TURISTA = 'turista-demo'

export function createMockBookingGateway({
  servicios,
  storage = globalThis.localStorage,
  clock = { now: () => new Date() },
  delayMs = 220,
  turistaId = DEMO_TURISTA,
  newId = () => (globalThis.crypto?.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`),
} = {}) {
  const ahora = () => clock.now()
  const err = (status, code, message) => new BookingError(code, message, { status, correlationId: `mock-${Math.random().toString(16).slice(2, 10)}` })
  const espera = (v) => (delayMs ? new Promise((res) => setTimeout(() => res(v), delayMs)) : Promise.resolve(v))
  const etag = (r) => `"${r.version}"`

  const read = () => { try { return JSON.parse(storage?.getItem(KEY)) } catch { return null } }
  const write = (db) => { try { storage?.setItem(KEY, JSON.stringify(db)) } catch { /* sin almacenamiento */ } }

  function seed() {
    const t = today(ahora())
    const mk = (servicio_id, dias, n, estado, extra = {}) => ({
      id: newId(), servicio_id, turista_id: turistaId, prestador_id: `prestador-${servicio_id}`,
      fecha_reserva: addDays(t, dias), numero_personas: n, estado, version: 1,
      creado_en: ahora().toISOString(), actualizado_en: ahora().toISOString(), expira_en: null, motivo: null, cancelada_por: null, ...extra,
    })
    const ids = Object.keys(servicios)
    const [a, b, c] = [ids[0], ids[1] ?? ids[0], ids[2] ?? ids[0]]
    return {
      reservas: [
        mk(a, 6, 2, 'CONFIRMADA', { version: 2 }),
        mk(b, 9, 3, 'SOLICITADA', { expira_en: plazoRespuesta(addDays(t, 9), ahora()) }),
        mk(c, -12, 2, 'FINALIZADA', { version: 3 }),
        mk(a, 14, 4, 'CANCELADA', { motivo: 'Cambio de planes', cancelada_por: 'Turista', version: 2 }),
      ],
      idem: {},
    }
  }

  function load() {
    let db = read()
    const primera = !db
    if (primera) db = seed()
    const antes = db.reservas
    db.reservas = antes.map((r) => liquidar(r, ahora()))
    // Los datos de ejemplo se guardan al primer uso: si no, cada lectura generaría identificadores nuevos
    if (primera || db.reservas.some((r, i) => r !== antes[i])) write(db)
    return db
  }

  const servicio = (id) => {
    const s = servicios[id]
    if (!s) throw err(404, 'NO_ENCONTRADO', 'El servicio no existe.')
    return s
  }

  /** Día operativo del servicio o null si no opera */
  function dia(db, id, fecha) {
    const s = servicio(id)
    if (s.cierra?.includes(weekday(fecha))) return null
    const total = s.capacidad ?? 10
    return {
      fecha,
      cupos_totales: total,
      cupos_disponibles: cuposDisponibles(total, cuposReservados(db.reservas, id, fecha)),
      tarifa_dia: s.recargo && weekday(fecha) === s.recargo.dia ? Math.round(s.fee * s.recargo.factor) : null,
    }
  }

  const propia = (db, id) => {
    const r = db.reservas.find((x) => x.id === id && x.turista_id === turistaId)
    if (!r) throw err(404, 'NO_ENCONTRADO', 'La reserva no existe.')
    return r
  }

  return {
    async consultarDisponibilidad(servicioId, desde, hasta) {
      const db = load(); servicio(servicioId)
      if (hasta < desde || hasta > addDays(desde, MAX_DIAS_CONSULTA)) throw err(400, 'VALIDACION', 'El rango máximo es de 62 días.')
      const dias = []
      for (let f = desde; f <= hasta; f = addDays(f, 1)) {
        const d = dia(db, servicioId, f)
        if (d) dias.push({ fecha: d.fecha, cupos_disponibles: d.cupos_disponibles, tarifa_dia: d.tarifa_dia })
      }
      return espera({ servicio_id: servicioId, dias })
    },

    async solicitarReserva(body, idempotencyKey) {
      const db = load()
      if (idempotencyKey && db.idem[idempotencyKey]) { // mismo intento = misma respuesta, sin repetir la operación
        const r = db.reservas.find((x) => x.id === db.idem[idempotencyKey]); return espera({ data: r, etag: etag(r) })
      }
      servicio(body.servicio_id)
      const errores = validarSolicitud({ fecha: body.fecha_reserva, personas: body.numero_personas }, { ahora: ahora() })
      if (errores.length) throw err(400, 'VALIDACION', errores[0])
      const d = dia(db, body.servicio_id, body.fecha_reserva)
      if (!d) throw err(409, 'DIA_NO_DISPONIBLE', `El prestador no opera el ${body.fecha_reserva}.`)
      if (esDuplicada(db.reservas, { turistaId, servicioId: body.servicio_id, fecha: body.fecha_reserva }))
        throw err(409, 'RESERVA_DUPLICADA', 'Ya tienes una reserva activa para ese servicio y fecha.')
      if (d.cupos_disponibles < body.numero_personas) throw err(409, 'CUPOS_INSUFICIENTES', `Solo quedan ${d.cupos_disponibles} cupos para el ${body.fecha_reserva}.`)
      const r = {
        id: newId(), servicio_id: body.servicio_id, turista_id: turistaId, prestador_id: `prestador-${body.servicio_id}`,
        fecha_reserva: body.fecha_reserva, numero_personas: body.numero_personas, estado: 'SOLICITADA',
        expira_en: plazoRespuesta(body.fecha_reserva, ahora()), motivo: null, cancelada_por: null, version: 1,
        creado_en: ahora().toISOString(), actualizado_en: ahora().toISOString(),
      }
      db.reservas.unshift(r)
      if (idempotencyKey) db.idem[idempotencyKey] = r.id
      write(db)
      return espera({ data: r, etag: etag(r) })
    },

    async misReservas({ estado, pagina = 1, tamano = 20 } = {}) {
      const db = load()
      const todas = db.reservas.filter((r) => r.turista_id === turistaId && (!estado || r.estado === estado)).sort((a, b) => b.creado_en.localeCompare(a.creado_en))
      return espera({ items: todas.slice((pagina - 1) * tamano, pagina * tamano), pagina, tamano, total: todas.length })
    },

    async modificarReserva(id, version, cambios) {
      const db = load()
      const r = propia(db, id)
      if (version == null) throw err(428, 'FALTA_IF_MATCH', 'Falta el encabezado If-Match.')
      if (`"${version}"` !== etag(r)) throw err(409, 'VERSION_DISTINTA', 'La reserva cambió en el servidor.')
      const decision = decisionModificar(r)
      if (!decision.permitido) throw err(409, decision.codigo, decision.mensaje)
      const fecha = cambios.fecha_reserva ?? r.fecha_reserva
      const n = cambios.numero_personas ?? r.numero_personas
      const errores = validarSolicitud({ fecha, personas: n }, { ahora: ahora() })
      if (errores.length) throw err(400, 'VALIDACION', errores[0])
      const d = dia(db, r.servicio_id, fecha)
      if (!d) throw err(409, 'DIA_NO_DISPONIBLE', `El prestador no opera el ${fecha}.`)
      const propios = fecha === r.fecha_reserva ? r.numero_personas : 0 // en el mismo día se reutilizan sus propios cupos
      if (d.cupos_disponibles + propios < n) throw err(409, 'CUPOS_INSUFICIENTES', `Solo quedan ${d.cupos_disponibles + propios} cupos para el ${fecha}.`)
      Object.assign(r, { fecha_reserva: fecha, numero_personas: n, version: r.version + 1, expira_en: plazoRespuesta(fecha, ahora()), actualizado_en: ahora().toISOString() })
      write(db)
      return espera({ data: r, etag: etag(r) })
    },

    async cancelarReserva(id, motivo) {
      const db = load()
      const r = propia(db, id)
      const decision = decisionCancelar(r, today(ahora()))
      if (!decision.permitido) throw err(409, decision.codigo, decision.mensaje)
      Object.assign(r, { estado: 'CANCELADA', expira_en: null, motivo: motivo || null, cancelada_por: 'Turista', version: r.version + 1, actualizado_en: ahora().toISOString() })
      write(db)
      return espera({ data: r, etag: etag(r) })
    },
  }
}
