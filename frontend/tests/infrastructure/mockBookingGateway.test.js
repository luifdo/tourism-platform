import { beforeEach, describe, expect, it } from 'vitest'
import { createMockBookingGateway } from '../../src/infrastructure/booking/mockBookingGateway.js'
import { assertBookingGateway } from '../../src/application/booking/ports.js'
import { addDays, today } from '../../src/domain/booking/dates.js'

/*
 * Pruebas del adaptador simulado como "servidor de reservas": comprueba que respeta el contrato
 * (códigos, ETag/If-Match, Idempotency-Key) y las reglas del dominio.
 */
const T0 = new Date('2026-10-26T15:00:00Z') // 26 de octubre, 10:00 en Bogotá
const servicios = {
  a: { fee: 100000, capacidad: 10, recargo: { dia: 6, factor: 1.2 } },
  b: { fee: 50000, capacidad: 5, cierra: [1] }, // cierra los lunes
}

let ahora, storage, gw
const memoria = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) } }
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }
beforeEach(() => {
  ahora = new Date(T0)
  storage = memoria()
  gw = createMockBookingGateway({ servicios, storage, clock: { now: () => ahora }, delayMs: 0, newId: (() => { let n = 0; return () => `id-${++n}` })() })
})
const cuposDe = async (id, fecha) => (await gw.consultarDisponibilidad(id, fecha, fecha)).dias[0]?.cupos_disponibles

it('implementa el puerto BookingGateway completo', () => {
  expect(assertBookingGateway(gw)).toBe(gw)
})

describe('consultarDisponibilidad', () => {
  it('devuelve los días operativos del rango y la tarifa del día cuando hay recargo', async () => {
    const r = await gw.consultarDisponibilidad('a', '2026-10-27', '2026-11-02')
    expect(r.dias).toHaveLength(7)
    expect(r.dias.find((d) => d.fecha === '2026-10-31')).toMatchObject({ cupos_disponibles: 10, tarifa_dia: 120000 }) // sábado
    expect(r.dias.find((d) => d.fecha === '2026-10-28').tarifa_dia).toBeNull()
  })
  it('omite los días en que el servicio no opera (lunes)', async () => {
    const r = await gw.consultarDisponibilidad('b', '2026-10-26', '2026-11-02')
    expect(r.dias.map((d) => d.fecha)).not.toContain('2026-10-26')
    expect(r.dias.map((d) => d.fecha)).not.toContain('2026-11-02')
  })
  it('rechaza un rango mayor a 62 días y un servicio inexistente', async () => {
    expect((await falla(gw.consultarDisponibilidad('a', '2026-10-27', '2027-02-01'))).code).toBe('VALIDACION')
    expect((await falla(gw.consultarDisponibilidad('zzz', '2026-10-27', '2026-10-28'))).code).toBe('NO_ENCONTRADO')
  })
})

describe('solicitarReserva', () => {
  const body = { servicio_id: 'a', fecha_reserva: '2026-11-10', numero_personas: 3 }

  it('crea la reserva SOLICITADA con plazo de respuesta y descuenta los cupos', async () => {
    const { data, etag } = await gw.solicitarReserva(body, 'k1')
    expect(data).toMatchObject({ estado: 'SOLICITADA', numero_personas: 3, version: 1, expira_en: '2026-10-28T15:00:00.000Z' })
    expect(etag).toBe('"1"')
    expect(await cuposDe('a', '2026-11-10')).toBe(7)
  })

  it('la misma Idempotency-Key devuelve la misma reserva y no vuelve a descontar', async () => {
    const r1 = await gw.solicitarReserva(body, 'misma')
    const r2 = await gw.solicitarReserva(body, 'misma')
    expect(r2.data.id).toBe(r1.data.id)
    expect(await cuposDe('a', '2026-11-10')).toBe(7)
  })

  it('una reserva activa del mismo servicio y fecha es RESERVA_DUPLICADA', async () => {
    await gw.solicitarReserva(body, 'k1')
    expect((await falla(gw.solicitarReserva(body, 'k2'))).code).toBe('RESERVA_DUPLICADA')
  })

  it('pedir más de los cupos es CUPOS_INSUFICIENTES e indica cuántos quedan', async () => {
    const e = await falla(gw.solicitarReserva({ ...body, numero_personas: 11 }, 'k'))
    expect(e).toMatchObject({ code: 'CUPOS_INSUFICIENTES', status: 409 })
    expect(e.message).toMatch(/10 cupos/)
  })

  it('un día en que no opera es DIA_NO_DISPONIBLE', async () => {
    expect((await falla(gw.solicitarReserva({ servicio_id: 'b', fecha_reserva: '2026-11-02', numero_personas: 1 }, 'k'))).code).toBe('DIA_NO_DISPONIBLE')
  })

  it('hoy o una fecha pasada es VALIDACION', async () => {
    expect((await falla(gw.solicitarReserva({ ...body, fecha_reserva: '2026-10-26' }, 'k'))).code).toBe('VALIDACION')
  })
})

describe('modificarReserva', () => {
  const crear = async () => (await gw.solicitarReserva({ servicio_id: 'a', fecha_reserva: '2026-11-10', numero_personas: 3 }, 'k')).data

  it('con la versión correcta aplica el cambio, sube la versión y reinicia el plazo', async () => {
    const r = await crear()
    const { data, etag } = await gw.modificarReserva(r.id, r.version, { numero_personas: 5 })
    expect(data).toMatchObject({ numero_personas: 5, version: 2 })
    expect(etag).toBe('"2"')
    expect(await cuposDe('a', '2026-11-10')).toBe(5)
  })

  it('al cambiar de fecha libera los cupos de la anterior', async () => {
    const r = await crear()
    await gw.modificarReserva(r.id, r.version, { fecha_reserva: '2026-11-12' })
    expect(await cuposDe('a', '2026-11-10')).toBe(10)
    expect(await cuposDe('a', '2026-11-12')).toBe(7)
  })

  it('una versión vieja es VERSION_DISTINTA y no cambia nada', async () => {
    const r = await crear()
    await gw.modificarReserva(r.id, r.version, { numero_personas: 4 })
    expect((await falla(gw.modificarReserva(r.id, r.version, { numero_personas: 6 }))).code).toBe('VERSION_DISTINTA')
    expect(await cuposDe('a', '2026-11-10')).toBe(6)
  })

  it('sin versión es FALTA_IF_MATCH (428)', async () => {
    const r = await crear()
    expect(await falla(gw.modificarReserva(r.id, undefined, { numero_personas: 4 }))).toMatchObject({ code: 'FALTA_IF_MATCH', status: 428 })
  })

  it('solo se modifica en SOLICITADA', async () => {
    const r = await crear()
    const cancelada = (await gw.cancelarReserva(r.id)).data
    expect((await falla(gw.modificarReserva(r.id, cancelada.version, { numero_personas: 2 }))).code).toBe('TRANSICION_INVALIDA')
  })
})

describe('cancelarReserva', () => {
  it('cancela, guarda el motivo y libera los cupos', async () => {
    const r = (await gw.solicitarReserva({ servicio_id: 'a', fecha_reserva: '2026-11-10', numero_personas: 3 }, 'k')).data
    const { data } = await gw.cancelarReserva(r.id, 'Cambio de planes')
    expect(data).toMatchObject({ estado: 'CANCELADA', motivo: 'Cambio de planes', cancelada_por: 'Turista', expira_en: null })
    expect(await cuposDe('a', '2026-11-10')).toBe(10)
  })

  it('cancelar dos veces es TRANSICION_INVALIDA', async () => {
    const r = (await gw.solicitarReserva({ servicio_id: 'a', fecha_reserva: '2026-11-10', numero_personas: 1 }, 'k')).data
    await gw.cancelarReserva(r.id)
    expect((await falla(gw.cancelarReserva(r.id))).code).toBe('TRANSICION_INVALIDA')
  })

  it('una reserva de otra persona o inexistente es NO_ENCONTRADO', async () => {
    expect((await falla(gw.cancelarReserva('no-existe'))).code).toBe('NO_ENCONTRADO')
  })
})

describe('reglas del tiempo sobre la reserva semilla confirmada', () => {
  const confirmada = async () => (await gw.misReservas({ estado: 'CONFIRMADA' })).items[0]

  it('el mismo día de la reserva ya es FUERA_DE_PLAZO', async () => {
    const r = await confirmada()
    ahora = new Date(`${r.fecha_reserva}T15:00:00Z`)
    expect((await falla(gw.cancelarReserva(r.id))).code).toBe('FUERA_DE_PLAZO')
  })

  it('pasada la fecha el sistema la FINALIZA', async () => {
    const r = await confirmada()
    ahora = new Date(`${addDays(r.fecha_reserva, 1)}T15:00:00Z`)
    expect((await gw.misReservas({ estado: 'FINALIZADA' })).items.map((x) => x.id)).toContain(r.id)
  })

  it('una SOLICITADA sin respuesta pasa a RECHAZADA al vencer su plazo y libera los cupos', async () => {
    const r = (await gw.solicitarReserva({ servicio_id: 'a', fecha_reserva: '2026-11-20', numero_personas: 4 }, 'k')).data
    ahora = new Date('2026-10-29T00:00:00Z')
    const lista = (await gw.misReservas({ estado: 'RECHAZADA' })).items
    expect(lista.find((x) => x.id === r.id)).toMatchObject({ estado: 'RECHAZADA', expira_en: null })
    expect(await cuposDe('a', '2026-11-20')).toBe(10)
  })
})

describe('misReservas', () => {
  it('filtra por estado y pagina, con las más recientes primero', async () => {
    const todas = await gw.misReservas()
    expect(todas.total).toBe(4)
    const pag1 = await gw.misReservas({ tamano: 3 })
    const pag2 = await gw.misReservas({ tamano: 3, pagina: 2 })
    expect(pag1.items).toHaveLength(3)
    expect(pag2.items).toHaveLength(1)
    expect((await gw.misReservas({ estado: 'CANCELADA' })).items.every((r) => r.estado === 'CANCELADA')).toBe(true)
  })

  it('persiste entre instancias que comparten el almacenamiento', async () => {
    await gw.solicitarReserva({ servicio_id: 'a', fecha_reserva: '2026-11-10', numero_personas: 1 }, 'k')
    const otra = createMockBookingGateway({ servicios, storage, clock: { now: () => ahora }, delayMs: 0 })
    expect((await otra.misReservas()).total).toBe(5)
    expect(today(ahora)).toBe('2026-10-26')
  })
})

describe('con sesión (el turista sale del usuario ingresado)', () => {
  let usuario
  const crear = () => createMockBookingGateway({ servicios, storage, clock: { now: () => ahora }, delayMs: 0, turistaId: () => usuario })

  it('sin sesión, las operaciones del usuario responden 401 NO_AUTENTICADO', async () => {
    usuario = null
    const g = crear()
    for (const op of [() => g.misReservas(), () => g.solicitarReserva({ servicio_id: 'a', fecha_reserva: '2026-11-10', numero_personas: 1 }, 'k'), () => g.cancelarReserva('x')])
      expect(await falla(op())).toMatchObject({ code: 'NO_AUTENTICADO', status: 401 })
  })

  it('la disponibilidad es pública: se consulta sin sesión', async () => {
    usuario = null
    const r = await crear().consultarDisponibilidad('a', '2026-10-27', '2026-10-29')
    expect(r.dias).toHaveLength(3)
  })

  it('cada usuario recibe sus propias reservas de ejemplo la primera vez, y no ve las de otro', async () => {
    usuario = 'ana'
    const g = crear()
    expect((await g.misReservas()).total).toBe(4)
    await g.solicitarReserva({ servicio_id: 'a', fecha_reserva: '2026-11-10', numero_personas: 2 }, 'ka')
    usuario = 'beto'
    expect((await g.misReservas()).total).toBe(4) // las suyas de ejemplo; no ve la de Ana
    usuario = 'ana'
    expect((await g.misReservas()).total).toBe(5)
  })

  it('los cupos son compartidos: lo que reserva uno lo ve descontado el otro', async () => {
    usuario = 'ana'
    const g = crear()
    await g.solicitarReserva({ servicio_id: 'a', fecha_reserva: '2026-11-10', numero_personas: 4 }, 'ka')
    usuario = 'beto'
    expect(await cuposDe('a', '2026-11-10')).toBe(6)
  })

  it('un usuario no puede tocar la reserva de otro (NO_ENCONTRADO)', async () => {
    usuario = 'ana'
    const g = crear()
    const r = (await g.solicitarReserva({ servicio_id: 'a', fecha_reserva: '2026-11-10', numero_personas: 1 }, 'ka')).data
    usuario = 'beto'
    expect((await falla(g.cancelarReserva(r.id))).code).toBe('NO_ENCONTRADO')
  })
})
