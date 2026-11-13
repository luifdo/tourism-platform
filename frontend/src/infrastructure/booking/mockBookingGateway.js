import { BookingError } from '../../domain/booking/errors.js'
import { decisionConfirmar, decisionRechazar, validarDia, validarMotivo, validarRango, diasDelRango } from '../../domain/booking/prestador.js'
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
 * `turistaId`: texto o función que devuelve el id del usuario con sesión. Las reservas son de todos (los cupos se
 * comparten) y cada usuario recibe sus propias reservas de ejemplo la primera vez que entra.
 * `rolUsuario`: texto o función con el rol de esa sesión ('Turista' por defecto). Los turistas piden y gestionan sus
 * reservas; los prestadores atienden las solicitudes y el calendario (como el servicio real: lo demás es 403). En el
 * simulador un prestador atiende TODOS los servicios de demostración. El calendario son días explícitos: un día que no
 * existe (o tiene 0 cupos) no se ofrece; el prestador puede abrir, editar y cerrar días, y eso cambia lo que ve el turista.
 */
const KEY = 'mock.bookings.v1'
const DEMO_TURISTA = 'turista-demo'

export function createMockBookingGateway({
  servicios,
  storage = globalThis.localStorage,
  clock = { now: () => new Date() },
  delayMs = 220,
  turistaId = DEMO_TURISTA,
  rolUsuario = 'Turista',
  newId = () => (globalThis.crypto?.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`),
} = {}) {
  const ahora = () => clock.now()
  const err = (status, code, message, data = null) => new BookingError(code, message, { status, correlationId: `mock-${Math.random().toString(16).slice(2, 10)}`, data })
  const espera = (v) => (delayMs ? new Promise((res) => setTimeout(() => res(v), delayMs)) : Promise.resolve(v))
  const etag = (r) => `"${r.version}"`
  // El turista sale de la sesión; sin sesión el servidor real respondería 401
  const turista = () => {
    const id = typeof turistaId === 'function' ? turistaId() : turistaId
    if (!id) throw err(401, 'NO_AUTENTICADO', 'Inicia sesión para continuar.')
    return id
  }

  const rol = () => (typeof rolUsuario === 'function' ? rolUsuario() : rolUsuario)
  const exigirRol = (esperado) => {
    if (rol() !== esperado) throw err(403, 'ROL_NO_PERMITIDO', `Esta operación es solo para el rol ${esperado}.`)
  }

  const read = () => { try { return JSON.parse(storage?.getItem(KEY)) } catch { return null } }
  const write = (db) => { try { storage?.setItem(KEY, JSON.stringify(db)) } catch { /* sin almacenamiento */ } }

  /** Reservas de ejemplo de un usuario (una confirmada, una solicitada, una finalizada y una cancelada) */
  function reservasDeEjemplo(usuarioId) {
    const t = today(ahora())
    const mk = (servicio_id, dias, n, estado, extra = {}) => ({
      id: newId(), servicio_id, turista_id: usuarioId, prestador_id: `prestador-${servicio_id}`,
      fecha_reserva: addDays(t, dias), numero_personas: n, estado, version: 1,
      creado_en: ahora().toISOString(), actualizado_en: ahora().toISOString(), expira_en: null, motivo: null, cancelada_por: null, ...extra,
    })
    const ids = Object.keys(servicios)
    const [a, b, c] = [ids[0], ids[1] ?? ids[0], ids[2] ?? ids[0]]
    return [
      mk(a, 6, 2, 'CONFIRMADA', { version: 2 }),
      mk(b, 9, 3, 'SOLICITADA', { expira_en: plazoRespuesta(addDays(t, 9), ahora()) }),
      mk(c, -12, 2, 'FINALIZADA', { version: 3 }),
      mk(a, 14, 4, 'CANCELADA', { motivo: 'Cambio de planes', cancelada_por: 'Turista', version: 2 }),
    ]
  }

  const VENTANA_SEMBRADO = 120 // días de calendario que el simulador abre por defecto, como si el prestador ya los hubiera abierto

  /** Abre por defecto los días que falten hasta hoy + 120 (sin tocar los que el prestador ya editó). true si cambió algo. */
  function asegurarCalendario(db, id) {
    const s = servicio(id)
    db.calendario ??= {}
    const objetivo = addDays(today(ahora()), VENTANA_SEMBRADO)
    const cal = (db.calendario[id] ??= { dias: {}, hasta: addDays(today(ahora()), -1) })
    if (cal.hasta >= objetivo) return false
    for (let f = addDays(cal.hasta, 1); f <= objetivo; f = addDays(f, 1)) {
      if (cal.dias[f] || s.cierra?.includes(weekday(f))) continue
      cal.dias[f] = { cupos_totales: s.capacidad ?? 10, tarifa_dia: s.recargo && weekday(f) === s.recargo.dia ? Math.round(s.fee * s.recargo.factor) : null, version: 1 }
    }
    cal.hasta = objetivo
    return true
  }

  /** Solicitudes de ejemplo para el panel del prestador, de turistas de demostración (una sola vez, la primera que entra uno). */
  function solicitudesDeEjemplo(db) {
    const t = today(ahora())
    const ids = Object.keys(servicios)
    const mk = (servicio_id, dias, n, estado, extra = {}) => ({
      id: newId(), servicio_id, turista_id: `turista-ejemplo-${newId().slice(0, 4)}`, prestador_id: `prestador-${servicio_id}`,
      fecha_reserva: addDays(t, dias), numero_personas: n, estado, version: 1,
      creado_en: ahora().toISOString(), actualizado_en: ahora().toISOString(), expira_en: null, motivo: null, cancelada_por: null, ...extra,
    })
    const ejemplos = [
      mk(ids[0], 1, 2, 'SOLICITADA', { expira_en: plazoRespuesta(addDays(t, 1), ahora()) }), // vence antes de que empiece el día: urgente
      mk(ids[1] ?? ids[0], 5, 4, 'SOLICITADA', { expira_en: plazoRespuesta(addDays(t, 5), ahora()) }),
      mk(ids[2] ?? ids[0], 8, 3, 'SOLICITADA', { expira_en: plazoRespuesta(addDays(t, 8), ahora()) }),
      mk(ids[0], 3, 2, 'CONFIRMADA', { version: 2 }),
      mk(ids[1] ?? ids[0], 11, 5, 'RECHAZADA', { motivo: 'Ese día el sendero está en mantenimiento.', version: 2 }),
    ]
    // Las que ocupan cupos se acomodan en el primer día con espacio: no deben pasar de la capacidad ni pisar lo ya reservado
    const reservadas = [...db.reservas]
    return ejemplos.flatMap((r) => {
      if (!['SOLICITADA', 'CONFIRMADA'].includes(r.estado)) return [r]
      for (let extra = 0; extra < 30; extra++) {
        const fecha = addDays(r.fecha_reserva, extra)
        const d = db.calendario?.[r.servicio_id]?.dias[fecha]
        if (d && d.cupos_totales - cuposReservados(reservadas, r.servicio_id, fecha) >= r.numero_personas) {
          const colocada = { ...r, fecha_reserva: fecha, ...(r.expira_en ? { expira_en: plazoRespuesta(fecha, ahora()) } : {}) }
          reservadas.push(colocada)
          return [colocada]
        }
      }
      return [] // no hay dónde ponerla sin pasar la capacidad
    })
  }

  /**
   * Lee la base. Con `conUsuario` exige sesión y, la primera vez que ese usuario entra, le crea sus reservas de
   * ejemplo (se guardan en ese momento: si no, cada lectura generaría identificadores nuevos).
   */
  function load(conUsuario = true) {
    const db = read() ?? { reservas: [], idem: {}, sembrados: {} }
    let cambio = !read()
    for (const id of Object.keys(servicios)) if (asegurarCalendario(db, id)) cambio = true
    if (conUsuario) {
      const id = turista()
      // Un turista recibe sus reservas de ejemplo; un prestador, las solicitudes de ejemplo (una vez, de turistas ficticios)
      if (rol() === 'Prestador') { if (!db.sembradoPrestador) { db.reservas.push(...solicitudesDeEjemplo(db)); db.sembradoPrestador = true; cambio = true } }
      else if (!db.sembrados[id]) { db.reservas.push(...reservasDeEjemplo(id)); db.sembrados[id] = true; cambio = true }
    }
    const antes = db.reservas
    db.reservas = antes.map((r) => liquidar(r, ahora()))
    if (cambio || db.reservas.some((r, i) => r !== antes[i])) write(db)
    return db
  }

  const servicio = (id) => {
    const s = servicios[id]
    if (!s) throw err(404, 'NO_ENCONTRADO', 'El servicio no existe.')
    return s
  }

  /** Día del calendario tal como lo ve el prestador (con lo reservado y su versión), o null si no existe. */
  function diaPrestador(db, id, fecha) {
    const d = db.calendario?.[id]?.dias[fecha]
    if (!d) return null
    const reservados = cuposReservados(db.reservas, id, fecha)
    return { fecha, cupos_totales: d.cupos_totales, cupos_disponibles: cuposDisponibles(d.cupos_totales, reservados), cupos_reservados: reservados, tarifa_dia: d.tarifa_dia ?? null, version: d.version }
  }

  /** Día operativo del servicio para el turista, o null si no se ofrece (no existe o tiene 0 cupos) */
  function dia(db, id, fecha) {
    servicio(id)
    const d = diaPrestador(db, id, fecha)
    if (!d || d.cupos_totales === 0) return null
    return { fecha, cupos_totales: d.cupos_totales, cupos_disponibles: d.cupos_disponibles, tarifa_dia: d.tarifa_dia }
  }

  const propia = (db, id) => {
    const r = db.reservas.find((x) => x.id === id && x.turista_id === turista())
    if (!r) throw err(404, 'NO_ENCONTRADO', 'La reserva no existe.')
    return r
  }

  return {
    async consultarDisponibilidad(servicioId, desde, hasta) {
      const db = load(false); servicio(servicioId)
      if (hasta < desde || hasta > addDays(desde, MAX_DIAS_CONSULTA)) throw err(400, 'VALIDACION', 'El rango máximo es de 62 días.')
      const dias = []
      for (let f = desde; f <= hasta; f = addDays(f, 1)) {
        const d = dia(db, servicioId, f)
        if (d) dias.push({ fecha: d.fecha, cupos_disponibles: d.cupos_disponibles, tarifa_dia: d.tarifa_dia })
      }
      return espera({ servicio_id: servicioId, dias })
    },

    async solicitarReserva(body, idempotencyKey) {
      exigirRol('Turista')
      const db = load()
      if (idempotencyKey && db.idem[idempotencyKey]) { // mismo intento = misma respuesta, sin repetir la operación
        const r = db.reservas.find((x) => x.id === db.idem[idempotencyKey]); return espera({ data: r, etag: etag(r) })
      }
      servicio(body.servicio_id)
      const errores = validarSolicitud({ fecha: body.fecha_reserva, personas: body.numero_personas }, { ahora: ahora() })
      if (errores.length) throw err(400, 'VALIDACION', errores[0])
      const d = dia(db, body.servicio_id, body.fecha_reserva)
      if (!d) throw err(409, 'DIA_NO_DISPONIBLE', `El prestador no opera el ${body.fecha_reserva}.`)
      if (esDuplicada(db.reservas, { turistaId: turista(), servicioId: body.servicio_id, fecha: body.fecha_reserva }))
        throw err(409, 'RESERVA_DUPLICADA', 'Ya tienes una reserva activa para ese servicio y fecha.')
      if (d.cupos_disponibles < body.numero_personas) throw err(409, 'CUPOS_INSUFICIENTES', `Solo quedan ${d.cupos_disponibles} cupos para el ${body.fecha_reserva}.`)
      const r = {
        id: newId(), servicio_id: body.servicio_id, turista_id: turista(), prestador_id: `prestador-${body.servicio_id}`,
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
      exigirRol('Turista')
      const db = load()
      const todas = db.reservas.filter((r) => r.turista_id === turista() && (!estado || r.estado === estado)).sort((a, b) => b.creado_en.localeCompare(a.creado_en))
      return espera({ items: todas.slice((pagina - 1) * tamano, pagina * tamano), pagina, tamano, total: todas.length })
    },

    async modificarReserva(id, version, cambios) {
      exigirRol('Turista')
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
      exigirRol('Turista')
      const db = load()
      const r = propia(db, id)
      const decision = decisionCancelar(r, today(ahora()))
      if (!decision.permitido) throw err(409, decision.codigo, decision.mensaje)
      Object.assign(r, { estado: 'CANCELADA', expira_en: null, motivo: motivo || null, cancelada_por: 'Turista', version: r.version + 1, actualizado_en: ahora().toISOString() })
      write(db)
      return espera({ data: r, etag: etag(r) })
    },

    /* ---------------- Panel del prestador (UC19, UC20) ---------------- */

    async solicitudesPrestador({ estado = 'SOLICITADA', servicio_id, desde, hasta, pagina = 1, tamano = 20 } = {}) {
      exigirRol('Prestador')
      const db = load()
      const todas = db.reservas
        .filter((r) => servicios[r.servicio_id] && r.estado === estado && (!servicio_id || r.servicio_id === servicio_id)
          && (!desde || r.fecha_reserva >= desde) && (!hasta || r.fecha_reserva <= hasta))
        // las pendientes, de la más urgente a la menos; las demás, de la fecha más reciente a la más antigua
        .sort((a, b) => (estado === 'SOLICITADA' ? (a.expira_en ?? '').localeCompare(b.expira_en ?? '') : b.fecha_reserva.localeCompare(a.fecha_reserva)))
      return espera({ items: todas.slice((pagina - 1) * tamano, pagina * tamano), pagina, tamano, total: todas.length })
    },

    async confirmarReserva(id) {
      exigirRol('Prestador')
      const db = load()
      const r = db.reservas.find((x) => x.id === id && servicios[x.servicio_id])
      if (!r) throw err(404, 'NO_ENCONTRADO', 'La reserva no existe.')
      const d = decisionConfirmar(r, ahora())
      if (!d.permitido) throw err(409, d.codigo, d.mensaje)
      Object.assign(r, { estado: 'CONFIRMADA', expira_en: null, version: r.version + 1, actualizado_en: ahora().toISOString() })
      write(db)
      return espera({ data: r, etag: etag(r) })
    },

    async rechazarReserva(id, motivo) {
      exigirRol('Prestador')
      const db = load()
      const r = db.reservas.find((x) => x.id === id && servicios[x.servicio_id])
      if (!r) throw err(404, 'NO_ENCONTRADO', 'La reserva no existe.')
      const m = validarMotivo(motivo)
      if (!m.ok) throw err(400, 'VALIDACION', 'El motivo debe tener entre 3 y 500 caracteres.')
      const d = decisionRechazar(r)
      if (!d.permitido) throw err(409, d.codigo, d.mensaje)
      Object.assign(r, { estado: 'RECHAZADA', expira_en: null, motivo: m.motivo, version: r.version + 1, actualizado_en: ahora().toISOString() }) // los cupos quedan libres solos: solo cuentan las activas
      write(db)
      return espera({ data: r, etag: etag(r) })
    },

    async calendarioServicio(servicioId, desde, hasta) {
      exigirRol('Prestador')
      const db = load(); servicio(servicioId)
      if (!desde || !hasta || hasta < desde) throw err(400, 'VALIDACION', 'El rango no es válido.')
      const dias = []
      for (let f = desde; f <= hasta; f = addDays(f, 1)) { const d = diaPrestador(db, servicioId, f); if (d) dias.push(d) }
      return espera({ servicio_id: servicioId, dias })
    },

    async abrirRangoCalendario(servicioId, body, idempotencyKey) {
      exigirRol('Prestador')
      const db = load(); const s = servicio(servicioId)
      db.idemPrestador ??= {}
      if (idempotencyKey && db.idemPrestador[idempotencyKey]) return espera(db.idemPrestador[idempotencyKey]) // mismo intento = misma respuesta
      const errores = validarRango({ desde: body.desde, hasta: body.hasta, diasSemana: body.dias_semana, cuposTotales: body.cupos_totales, tarifaDia: body.tarifa_dia }, { ahora: ahora() })
      if (errores.length) throw err(400, 'VALIDACION', 'Los datos del rango no son válidos.')
      if (body.cupos_totales > (s.capacidad ?? Infinity)) throw err(422, 'SUPERA_AFORO', `Los cupos superan la capacidad de carga del servicio (${s.capacidad}).`)
      const cal = db.calendario[servicioId]
      const creados = []; const omitidos = []
      for (const f of diasDelRango({ desde: body.desde, hasta: body.hasta, diasSemana: body.dias_semana })) {
        if (cal.dias[f]) { omitidos.push(f); continue }
        cal.dias[f] = { cupos_totales: body.cupos_totales, tarifa_dia: body.tarifa_dia ?? null, version: 1 }
        creados.push(f)
      }
      const respuesta = { creados, omitidos }
      if (idempotencyKey) db.idemPrestador[idempotencyKey] = respuesta
      write(db)
      return espera(respuesta)
    },

    async guardarDiaCalendario(servicioId, fecha, body, { version = null, idempotencyKey } = {}) {
      exigirRol('Prestador')
      const db = load(); const s = servicio(servicioId)
      db.idemPrestador ??= {}
      if (idempotencyKey && db.idemPrestador[idempotencyKey]) return espera(db.idemPrestador[idempotencyKey])
      if (!/^\d{4}-\d{2}-\d{2}$/.test(fecha)) throw err(400, 'VALIDACION', 'La fecha no es válida.')
      const cal = db.calendario[servicioId]
      const actual = cal.dias[fecha]
      const reservados = cuposReservados(db.reservas, servicioId, fecha)
      const errores = validarDia({ cuposTotales: body.cupos_totales, tarifaDia: body.tarifa_dia }, { reservados: 0 }) // lo reservado y el aforo tienen su propio código
      if (errores.length) throw err(400, 'VALIDACION', 'Los datos del día no son válidos.')
      if (version == null) { // sin If-Match solo se crea
        if (actual) throw err(409, 'DIA_EXISTENTE', `El día ${fecha} ya existe: edítalo con su versión.`)
      } else {
        if (!actual) throw err(404, 'NO_ENCONTRADO', 'Ese día no existe.')
        if (String(version) !== String(actual.version)) throw err(409, 'VERSION_DISTINTA', 'El día cambió en el servidor.', { version_actual: actual.version, actual: diaPrestador(db, servicioId, fecha) })
        if (body.cupos_totales < reservados) throw err(409, 'CUPOS_COMPROMETIDOS', `Ya hay ${reservados} cupos reservados ese día.`)
      }
      if (body.cupos_totales > (s.capacidad ?? Infinity)) throw err(422, 'SUPERA_AFORO', `Los cupos superan la capacidad de carga del servicio (${s.capacidad}).`)
      cal.dias[fecha] = { cupos_totales: body.cupos_totales, tarifa_dia: body.tarifa_dia ?? null, version: actual ? actual.version + 1 : 1 }
      const dia = diaPrestador(db, servicioId, fecha)
      const respuesta = { data: dia, etag: `"${dia.version}"`, creado: !actual }
      if (idempotencyKey) db.idemPrestador[idempotencyKey] = respuesta
      write(db)
      return espera(respuesta)
    },
  }
}
