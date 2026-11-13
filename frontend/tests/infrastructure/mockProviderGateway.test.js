import { beforeEach, describe, expect, it } from 'vitest'
import { createMockBookingGateway } from '../../src/infrastructure/booking/mockBookingGateway.js'
import { assertProviderGateway } from '../../src/application/provider/ports.js'
import { addDays, today, weekday } from '../../src/domain/booking/dates.js'

/* El simulador debe responder como booking-service para el prestador: roles, calendario explícito, versiones e idempotencia. */
const T0 = new Date('2026-11-12T15:00:00Z') // 10:00 del jueves 12 de noviembre en Bogotá
const servicios = {
  a: { fee: 100000, capacidad: 10, recargo: { dia: 6, factor: 1.2 } },
  b: { fee: 50000, capacidad: 5, cierra: [1] }, // cierra los lunes
}
const memoria = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) } }
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }

let ahora, storage, usuario, rol, gw
const crear = () => createMockBookingGateway({ servicios, storage, clock: { now: () => ahora }, delayMs: 0, turistaId: () => usuario, rolUsuario: () => rol, newId: (() => { let n = 0; return () => `id-${++n}` })() })
const como = (u, r) => { usuario = u; rol = r }
beforeEach(() => {
  ahora = new Date(T0); storage = memoria(); como('turista-1', 'Turista'); gw = crear()
})
const mañana = () => addDays(today(ahora), 1)
const solicitar = (servicio_id, fecha, n = 2, clave = `k-${Math.random()}`) => gw.solicitarReserva({ servicio_id, fecha_reserva: fecha, numero_personas: n }, clave)

describe('simulador: roles', () => {
  it('implementa el puerto del prestador', () => expect(assertProviderGateway(gw)).toBe(gw))

  it('el turista no puede usar el panel del prestador: 403 ROL_NO_PERMITIDO', async () => {
    for (const op of [() => gw.solicitudesPrestador(), () => gw.confirmarReserva('x'), () => gw.rechazarReserva('x', 'motivo'),
      () => gw.calendarioServicio('a', mañana(), addDays(mañana(), 5)), () => gw.abrirRangoCalendario('a', {}, 'k'), () => gw.guardarDiaCalendario('a', mañana(), { cupos_totales: 3 }, {})])
      expect(await falla(op())).toMatchObject({ code: 'ROL_NO_PERMITIDO', status: 403 })
  })

  it('el prestador no pide ni gestiona reservas de turista', async () => {
    como('prestador-1', 'Prestador')
    expect((await falla(solicitar('a', mañana()))).code).toBe('ROL_NO_PERMITIDO')
    expect((await falla(gw.misReservas())).code).toBe('ROL_NO_PERMITIDO')
  })

  it('sin sesión el servicio responde 401', async () => {
    como(null, 'Prestador')
    expect(await falla(gw.solicitudesPrestador())).toMatchObject({ status: 401, code: 'NO_AUTENTICADO' })
  })
})

describe('simulador: solicitudes (UC20)', () => {
  it('un prestador que entra por primera vez ve solicitudes de ejemplo, de la más urgente a la menos', async () => {
    como('prestador-1', 'Prestador')
    const r = await gw.solicitudesPrestador()
    expect(r.items.length).toBeGreaterThanOrEqual(3)
    expect(r.items.every((x) => x.estado === 'SOLICITADA')).toBe(true)
    const vencen = r.items.map((x) => x.expira_en)
    expect(vencen).toEqual([...vencen].sort())
    expect(await gw.solicitudesPrestador()).toEqual(r) // la semilla se guarda: ids estables, no se duplica
  })

  it('ve lo que piden los turistas, y filtra por estado y por servicio', async () => {
    await solicitar('b', addDays(mañana(), 6), 3)
    como('prestador-1', 'Prestador')
    const todas = await gw.solicitudesPrestador()
    const nueva = todas.items.find((x) => x.turista_id === 'turista-1' && x.servicio_id === 'b' && x.fecha_reserva === addDays(mañana(), 6))
    expect(nueva).toMatchObject({ estado: 'SOLICITADA', numero_personas: 3 })
    expect((await gw.solicitudesPrestador({ servicio_id: 'b' })).items.every((x) => x.servicio_id === 'b')).toBe(true)
    expect((await gw.solicitudesPrestador({ estado: 'CONFIRMADA' })).items.every((x) => x.estado === 'CONFIRMADA')).toBe(true)
  })

  it('pagina', async () => {
    como('prestador-1', 'Prestador')
    const total = (await gw.solicitudesPrestador()).total
    const p1 = await gw.solicitudesPrestador({ pagina: 1, tamano: 2 })
    expect(p1.items).toHaveLength(2)
    expect(p1.total).toBe(total)
  })

  it('confirmar pasa a CONFIRMADA, quita el plazo y sube la versión; el turista lo ve', async () => {
    const { data: r } = await solicitar('a', addDays(mañana(), 4), 2)
    como('prestador-1', 'Prestador')
    const { data, etag } = await gw.confirmarReserva(r.id)
    expect(data).toMatchObject({ estado: 'CONFIRMADA', expira_en: null, version: 2 })
    expect(etag).toBe('"2"')
    como('turista-1', 'Turista')
    expect((await gw.misReservas()).items.find((x) => x.id === r.id).estado).toBe('CONFIRMADA')
  })

  it('confirmar dos veces o una que el turista canceló: 409 TRANSICION_INVALIDA', async () => {
    const { data: r } = await solicitar('a', addDays(mañana(), 20), 2) // días sin reservas de ejemplo del turista
    const { data: c } = await solicitar('a', addDays(mañana(), 21), 1)
    await gw.cancelarReserva(c.id, 'no voy')
    como('prestador-1', 'Prestador')
    await gw.confirmarReserva(r.id)
    expect(await falla(gw.confirmarReserva(r.id))).toMatchObject({ code: 'TRANSICION_INVALIDA', status: 409 })
    expect(await falla(gw.confirmarReserva(c.id))).toMatchObject({ code: 'TRANSICION_INVALIDA', status: 409 })
  })

  it('una reserva que no existe es 404', async () => {
    como('prestador-1', 'Prestador')
    expect((await falla(gw.confirmarReserva('nada'))).status).toBe(404)
  })

  it('rechazar exige un motivo, pasa a RECHAZADA y LIBERA los cupos', async () => {
    const fecha = addDays(mañana(), 4)
    const { data: r } = await solicitar('b', fecha, 5) // todo el cupo del día
    como('prestador-1', 'Prestador')
    expect((await falla(gw.rechazarReserva(r.id, 'ab'))).status).toBe(400)
    const antes = (await gw.calendarioServicio('b', fecha, fecha)).dias[0]
    expect(antes).toMatchObject({ cupos_reservados: 5, cupos_disponibles: 0 })
    const { data } = await gw.rechazarReserva(r.id, 'El sendero está en mantenimiento.')
    expect(data).toMatchObject({ estado: 'RECHAZADA', motivo: 'El sendero está en mantenimiento.' })
    expect((await gw.calendarioServicio('b', fecha, fecha)).dias[0]).toMatchObject({ cupos_reservados: 0, cupos_disponibles: 5 })
  })

  it('sin respuesta, la solicitud vence sola (RECHAZADA con el motivo del sistema)', async () => {
    const { data: r } = await solicitar('a', addDays(mañana(), 4), 1)
    ahora = new Date(ahora.getTime() + 49 * 3600e3)
    como('prestador-1', 'Prestador')
    expect((await gw.solicitudesPrestador({ estado: 'RECHAZADA' })).items.find((x) => x.id === r.id)?.motivo).toMatch(/plazo/i)
  })
})

describe('simulador: calendario (UC19)', () => {
  beforeEach(() => como('prestador-1', 'Prestador'))
  const dia = async (id, fecha) => (await gw.calendarioServicio(id, fecha, fecha)).dias[0]

  it('trae los días abiertos con totales, reservados, libres, tarifa y versión; un servicio que cierra los lunes no los abre', async () => {
    const r = await gw.calendarioServicio('b', mañana(), addDays(mañana(), 13))
    expect(r.dias.every((d) => weekday(d.fecha) !== 1)).toBe(true)
    expect(r.dias[0]).toMatchObject({ cupos_totales: 5, cupos_reservados: 0, cupos_disponibles: 5, version: 1 })
    const conRecargo = (await gw.calendarioServicio('a', mañana(), addDays(mañana(), 13))).dias.find((d) => weekday(d.fecha) === 6)
    expect(conRecargo.tarifa_dia).toBe(120000)
  })

  it('un servicio que no existe es 404', async () => {
    expect((await falla(gw.calendarioServicio('zzz', mañana(), mañana()))).status).toBe(404)
  })

  describe('guardar un día', () => {
    it('crear un día que ya existe sin If-Match: 409 DIA_EXISTENTE', async () => {
      expect(await falla(gw.guardarDiaCalendario('a', mañana(), { cupos_totales: 3 }, {}))).toMatchObject({ code: 'DIA_EXISTENTE', status: 409 })
    })

    it('crea un día fuera de la ventana inicial (201, versión 1) y el turista lo ve', async () => {
      const lejos = addDays(today(ahora), 200)
      const r = await gw.guardarDiaCalendario('a', lejos, { cupos_totales: 6, tarifa_dia: 80000 }, { idempotencyKey: 'k1' })
      expect(r).toMatchObject({ creado: true, etag: '"1"', data: { fecha: lejos, cupos_totales: 6, tarifa_dia: 80000, version: 1 } })
    })

    it('edita con la versión vista: sube la versión y cambia lo que ve el turista', async () => {
      const fecha = addDays(mañana(), 3)
      const antes = await dia('a', fecha)
      const r = await gw.guardarDiaCalendario('a', fecha, { cupos_totales: 4, tarifa_dia: 99000 }, { version: antes.version, idempotencyKey: 'k2' })
      expect(r).toMatchObject({ creado: false, etag: '"2"', data: { cupos_totales: 4, version: 2, tarifa_dia: 99000 } })
      const disp = (await gw.consultarDisponibilidad('a', fecha, fecha)).dias[0] // la disponibilidad es pública
      expect(disp).toMatchObject({ cupos_disponibles: 4, tarifa_dia: 99000 })
    })

    it('con una versión vieja: 409 VERSION_DISTINTA con `version_actual` y el día `actual`', async () => {
      const fecha = addDays(mañana(), 3)
      await gw.guardarDiaCalendario('a', fecha, { cupos_totales: 7 }, { version: 1, idempotencyKey: 'k3' }) // otra pestaña ya lo cambió
      const e = await falla(gw.guardarDiaCalendario('a', fecha, { cupos_totales: 3 }, { version: 1, idempotencyKey: 'k4' }))
      expect(e).toMatchObject({ code: 'VERSION_DISTINTA', status: 409 })
      expect(e.data.version_actual).toBe(2)
      expect(e.data.actual).toMatchObject({ fecha, cupos_totales: 7, version: 2 })
    })

    it('no deja menos cupos que los ya reservados: 409 CUPOS_COMPROMETIDOS', async () => {
      const fecha = addDays(mañana(), 3)
      como('turista-1', 'Turista'); await solicitar('a', fecha, 6); como('prestador-1', 'Prestador')
      expect(await falla(gw.guardarDiaCalendario('a', fecha, { cupos_totales: 5 }, { version: 1 }))).toMatchObject({ code: 'CUPOS_COMPROMETIDOS', status: 409 })
      expect((await gw.guardarDiaCalendario('a', fecha, { cupos_totales: 6 }, { version: 1 })).data.cupos_disponibles).toBe(0) // justo lo reservado sí
    })

    it('no supera el aforo oficial: 422 SUPERA_AFORO', async () => {
      expect(await falla(gw.guardarDiaCalendario('a', addDays(mañana(), 3), { cupos_totales: 11 }, { version: 1 }))).toMatchObject({ code: 'SUPERA_AFORO', status: 422 })
    })

    it('con 0 cupos el día se cierra y el turista ya no lo ve', async () => {
      const fecha = addDays(mañana(), 3)
      await gw.guardarDiaCalendario('a', fecha, { cupos_totales: 0 }, { version: 1 })
      expect((await gw.consultarDisponibilidad('a', fecha, fecha)).dias).toEqual([])
      como('turista-1', 'Turista')
      expect((await falla(solicitar('a', fecha, 1))).code).toBe('DIA_NO_DISPONIBLE')
    })

    it('el mismo intento (misma Idempotency-Key) devuelve la misma respuesta y no repite la operación', async () => {
      const fecha = addDays(today(ahora), 250)
      const a = await gw.guardarDiaCalendario('a', fecha, { cupos_totales: 3 }, { idempotencyKey: 'igual' })
      const b = await gw.guardarDiaCalendario('a', fecha, { cupos_totales: 3 }, { idempotencyKey: 'igual' })
      expect(b).toEqual(a)
      expect(await falla(gw.guardarDiaCalendario('a', fecha, { cupos_totales: 3 }, { idempotencyKey: 'otra' }))).toMatchObject({ code: 'DIA_EXISTENTE' })
    })

    it('valida el cuerpo y la fecha: 400', async () => {
      expect((await falla(gw.guardarDiaCalendario('a', 'mañana', { cupos_totales: 3 }, {}))).status).toBe(400)
      expect((await falla(gw.guardarDiaCalendario('a', addDays(mañana(), 3), { cupos_totales: -1 }, { version: 1 }))).status).toBe(400)
    })
  })

  describe('abrir un rango', () => {
    const lejos = () => addDays(today(ahora), 300)
    it('crea los días que coinciden con los días de la semana y omite los que ya existían', async () => {
      const desde = lejos(); const hasta = addDays(desde, 13)
      const r1 = await gw.abrirRangoCalendario('a', { desde, hasta, dias_semana: [6, 7], cupos_totales: 4, tarifa_dia: null }, 'rango-1')
      expect(r1.creados).toHaveLength(4)
      expect(r1.creados.every((f) => [6, 7].includes(weekday(f)))).toBe(true)
      expect(r1.omitidos).toEqual([])
      const r2 = await gw.abrirRangoCalendario('a', { desde, hasta, cupos_totales: 4 }, 'rango-2') // todos los días: los 4 ya existían
      expect(r2.omitidos).toHaveLength(4)
      expect(r2.creados).toHaveLength(10)
    })
    it('mismo intento = misma respuesta', async () => {
      const desde = lejos()
      const a = await gw.abrirRangoCalendario('a', { desde, hasta: addDays(desde, 2), cupos_totales: 2 }, 'misma')
      const b = await gw.abrirRangoCalendario('a', { desde, hasta: addDays(desde, 2), cupos_totales: 2 }, 'misma')
      expect(b).toEqual(a)
    })
    it('un rango inválido es 400 y superar el aforo, 422', async () => {
      const desde = lejos()
      expect((await falla(gw.abrirRangoCalendario('a', { desde, hasta: addDays(desde, -1), cupos_totales: 2 }, 'k'))).status).toBe(400)
      expect(await falla(gw.abrirRangoCalendario('a', { desde, hasta: addDays(desde, 2), cupos_totales: 99 }, 'k'))).toMatchObject({ code: 'SUPERA_AFORO', status: 422 })
    })
  })
})
