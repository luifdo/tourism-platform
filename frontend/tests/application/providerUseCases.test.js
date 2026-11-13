import { beforeEach, describe, expect, it, vi } from 'vitest'
import { BookingError } from '../../src/domain/booking/errors.js'
import { createProviderUseCases } from '../../src/application/provider/useCases.js'
import { assertProviderGateway, PROVIDER_GATEWAY_METHODS } from '../../src/application/provider/ports.js'

const AHORA = new Date('2026-11-12T15:00:00Z')
const solicitud = (extra = {}) => ({ id: 'r1', servicio_id: 's1', estado: 'SOLICITADA', version: 1, expira_en: new Date(AHORA.getTime() + 10 * 3600e3).toISOString(), ...extra })
const dia = { fecha: '2026-11-20', cupos_totales: 10, cupos_disponibles: 10, cupos_reservados: 0, tarifa_dia: null, version: 1 }
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }

let gw, autenticado, esperar, uc
beforeEach(() => {
  autenticado = true
  gw = {
    solicitudesPrestador: vi.fn(async () => ({ items: [solicitud()], pagina: 1, tamano: 20, total: 1 })),
    confirmarReserva: vi.fn(async () => ({ data: solicitud({ estado: 'CONFIRMADA' }), etag: '"2"' })),
    rechazarReserva: vi.fn(async () => ({ data: solicitud({ estado: 'RECHAZADA', motivo: 'x' }), etag: '"2"' })),
    calendarioServicio: vi.fn(async () => ({ servicio_id: 's1', dias: [dia] })),
    abrirRangoCalendario: vi.fn(async () => ({ creados: ['2026-11-20'], omitidos: [] })),
    guardarDiaCalendario: vi.fn(async () => ({ data: dia, etag: '"1"', creado: true })),
  }
  esperar = vi.fn(async () => {})
  uc = createProviderUseCases({ gateway: gw, session: { isAuthenticated: () => autenticado }, clock: { now: () => AHORA }, esperar })
})

describe('puerto ProviderGateway', () => {
  it('rechaza un adaptador incompleto indicando qué le falta', () => {
    expect(() => assertProviderGateway({ solicitudesPrestador() {} })).toThrow(/confirmarReserva/)
    expect(() => createProviderUseCases({ gateway: {}, session: {}, clock: {} })).toThrow(TypeError)
    const g = Object.fromEntries(PROVIDER_GATEWAY_METHODS.map((m) => [m, () => {}]))
    expect(assertProviderGateway(g)).toBe(g)
  })
})

describe('sin sesión nada llega al servidor', () => {
  it('todas las operaciones piden iniciar sesión (NO_AUTENTICADO, 401)', async () => {
    autenticado = false
    for (const op of [
      () => uc.solicitudes(), () => uc.confirmar(solicitud()), () => uc.rechazar(solicitud(), 'sin cupo'), () => uc.calendario('s1', { desde: 'a', hasta: 'b' }),
      () => uc.abrirRango('s1', { desde: '2026-11-13', hasta: '2026-11-20', cuposTotales: 5 }), () => uc.guardarDia('s1', '2026-11-20', { cuposTotales: 5 }),
    ]) expect(await falla(op())).toMatchObject({ code: 'NO_AUTENTICADO', status: 401 })
    for (const m of PROVIDER_GATEWAY_METHODS) expect(gw[m]).not.toHaveBeenCalled()
  })
})

describe('solicitudes (UC20)', () => {
  it('por defecto pide las SOLICITADA, de a 20', async () => {
    await uc.solicitudes()
    expect(gw.solicitudesPrestador).toHaveBeenCalledWith({ estado: 'SOLICITADA', servicio_id: undefined, desde: undefined, hasta: undefined, pagina: 1, tamano: 20 })
  })
  it('pasa los filtros con el nombre del contrato', async () => {
    await uc.solicitudes({ estado: 'CONFIRMADA', servicioId: 's1', desde: '2026-11-01', hasta: '2026-11-30', pagina: 2, tamano: 5 })
    expect(gw.solicitudesPrestador).toHaveBeenCalledWith({ estado: 'CONFIRMADA', servicio_id: 's1', desde: '2026-11-01', hasta: '2026-11-30', pagina: 2, tamano: 5 })
  })
})

describe('confirmar', () => {
  it('confirma una pendiente y devuelve la reserva con su ETag', async () => {
    const r = await uc.confirmar(solicitud())
    expect(gw.confirmarReserva).toHaveBeenCalledWith('r1')
    expect(r).toMatchObject({ reserva: { estado: 'CONFIRMADA' }, etag: '"2"' })
  })
  it('no llama al servidor si ya no está pendiente o venció el plazo', async () => {
    expect((await falla(uc.confirmar(solicitud({ estado: 'CANCELADA' })))).code).toBe('TRANSICION_INVALIDA')
    expect((await falla(uc.confirmar(solicitud({ expira_en: new Date(AHORA.getTime() - 1000).toISOString() })))).code).toBe('PLAZO_VENCIDO')
    expect(gw.confirmarReserva).not.toHaveBeenCalled()
  })
  it('un 409 del servidor se propaga (puede haber cambiado desde que se cargó la lista)', async () => {
    gw.confirmarReserva.mockRejectedValue(new BookingError('TRANSICION_INVALIDA', 'ya no', { status: 409 }))
    expect((await falla(uc.confirmar(solicitud()))).code).toBe('TRANSICION_INVALIDA')
  })
})

describe('rechazar', () => {
  it('exige el motivo y lo manda recortado', async () => {
    await uc.rechazar(solicitud(), '  Sendero cerrado  ')
    expect(gw.rechazarReserva).toHaveBeenCalledWith('r1', 'Sendero cerrado')
  })
  it('sin motivo válido no llama al servidor', async () => {
    for (const m of ['', '  ', 'ab', 'a'.repeat(501), null]) expect((await falla(uc.rechazar(solicitud(), m))).code).toBe('MOTIVO_INVALIDO')
    expect(gw.rechazarReserva).not.toHaveBeenCalled()
  })
  it('solo una pendiente se rechaza', async () => {
    expect((await falla(uc.rechazar(solicitud({ estado: 'CONFIRMADA' }), 'sin cupo'))).code).toBe('TRANSICION_INVALIDA')
    expect(gw.rechazarReserva).not.toHaveBeenCalled()
  })
})

describe('calendario (UC19)', () => {
  it('trae los días del rango', async () => {
    expect((await uc.calendario('s1', { desde: '2026-11-13', hasta: '2026-12-12' })).dias).toHaveLength(1)
    expect(gw.calendarioServicio).toHaveBeenCalledWith('s1', '2026-11-13', '2026-12-12')
  })

  describe('abrirRango', () => {
    const rango = { desde: '2026-11-13', hasta: '2026-11-20', diasSemana: [6, 7], cuposTotales: 8, tarifaDia: 90000 }
    it('manda el cuerpo del contrato con la Idempotency-Key', async () => {
      const r = await uc.abrirRango('s1', rango, { idempotencyKey: 'k-1' })
      expect(gw.abrirRangoCalendario).toHaveBeenCalledWith('s1', { desde: '2026-11-13', hasta: '2026-11-20', dias_semana: [6, 7], cupos_totales: 8, tarifa_dia: 90000 }, 'k-1')
      expect(r.creados).toEqual(['2026-11-20'])
    })
    it('sin días de la semana no manda dias_semana (= todos los días)', async () => {
      await uc.abrirRango('s1', { ...rango, diasSemana: undefined }, { idempotencyKey: 'k' })
      expect(gw.abrirRangoCalendario.mock.calls[0][1]).not.toHaveProperty('dias_semana')
    })
    it('un rango inválido no llega al servidor y trae los errores por campo', async () => {
      const e = await falla(uc.abrirRango('s1', { ...rango, desde: '2026-11-01' }, { idempotencyKey: 'k' }))
      expect(e).toMatchObject({ code: 'VALIDACION', status: 400 })
      expect(e.campos).toEqual([{ campo: 'desde', codigo: 'FECHA_PASADA' }])
      expect(gw.abrirRangoCalendario).not.toHaveBeenCalled()
    })
    it('con el aforo conocido, superarlo no llega al servidor', async () => {
      const e = await falla(uc.abrirRango('s1', { ...rango, cuposTotales: 30 }, { idempotencyKey: 'k', aforo: 20 }))
      expect(e.campos[0]).toEqual({ campo: 'cuposTotales', codigo: 'SUPERA_AFORO' })
    })
  })

  describe('guardarDia', () => {
    it('sin versión crea el día (el servidor responde 201)', async () => {
      const r = await uc.guardarDia('s1', '2026-11-20', { cuposTotales: 10 }, { idempotencyKey: 'k' })
      expect(gw.guardarDiaCalendario).toHaveBeenCalledWith('s1', '2026-11-20', { cupos_totales: 10, tarifa_dia: null }, { version: null, idempotencyKey: 'k' })
      expect(r).toMatchObject({ dia, creado: true, etag: '"1"' })
    })
    it('con la versión vista lo edita', async () => {
      await uc.guardarDia('s1', '2026-11-20', { cuposTotales: 6, tarifaDia: 70000 }, { version: 3, idempotencyKey: 'k' })
      expect(gw.guardarDiaCalendario.mock.calls[0][3]).toEqual({ version: 3, idempotencyKey: 'k' })
    })
    it('no baja de lo ya reservado ni sube del aforo, sin llamar al servidor', async () => {
      expect((await falla(uc.guardarDia('s1', '2026-11-20', { cuposTotales: 2 }, { version: 1, reservados: 5 }))).campos).toEqual([{ campo: 'cuposTotales', codigo: 'CUPOS_COMPROMETIDOS' }])
      expect((await falla(uc.guardarDia('s1', '2026-11-20', { cuposTotales: 25 }, { aforo: 20 }))).campos).toEqual([{ campo: 'cuposTotales', codigo: 'SUPERA_AFORO' }])
      expect(gw.guardarDiaCalendario).not.toHaveBeenCalled()
    })
    it('el 409 VERSION_DISTINTA trae lo que hay ahora en `data` para mostrar el conflicto', async () => {
      const actual = { ...dia, cupos_totales: 4, version: 5 }
      gw.guardarDiaCalendario.mockRejectedValue(new BookingError('VERSION_DISTINTA', 'cambió', { status: 409, data: { version_actual: 5, actual } }))
      const e = await falla(uc.guardarDia('s1', '2026-11-20', { cuposTotales: 6 }, { version: 2, idempotencyKey: 'k' }))
      expect(e.data).toEqual({ version_actual: 5, actual })
    })
  })

  describe('reintentos con la MISMA Idempotency-Key (INTEGRACION.md §2.3)', () => {
    it.each(['PETICION_EN_PROCESO', 'IDEMPOTENCIA_NO_DISPONIBLE'])('un %s se reintenta con la misma clave, esperando entre intentos', async (codigo) => {
      gw.guardarDiaCalendario
        .mockRejectedValueOnce(new BookingError(codigo, 'x', { status: codigo === 'PETICION_EN_PROCESO' ? 409 : 503 }))
        .mockResolvedValueOnce({ data: dia, etag: '"1"', creado: true })
      const r = await uc.guardarDia('s1', '2026-11-20', { cuposTotales: 10 }, { idempotencyKey: 'misma' })
      expect(r.creado).toBe(true)
      expect(gw.guardarDiaCalendario).toHaveBeenCalledTimes(2)
      expect(gw.guardarDiaCalendario.mock.calls.map((c) => c[3].idempotencyKey)).toEqual(['misma', 'misma'])
      expect(esperar).toHaveBeenCalledTimes(1)
    })
    it('si sigue en proceso, reintenta hasta 3 veces y entonces propaga el error', async () => {
      gw.abrirRangoCalendario.mockRejectedValue(new BookingError('PETICION_EN_PROCESO', 'x', { status: 409 }))
      const e = await falla(uc.abrirRango('s1', { desde: '2026-11-13', hasta: '2026-11-20', cuposTotales: 5 }, { idempotencyKey: 'k' }))
      expect(e.code).toBe('PETICION_EN_PROCESO')
      expect(gw.abrirRangoCalendario).toHaveBeenCalledTimes(4) // el intento y 3 reintentos
      expect(esperar.mock.calls.map((c) => c[0])).toEqual([1500, 3000, 6000])
    })
    it('los demás errores no se reintentan (un 409 de conflicto o un 422 ya son la respuesta)', async () => {
      for (const codigo of ['VERSION_DISTINTA', 'SUPERA_AFORO', 'DIA_EXISTENTE', 'SIN_CONEXION']) {
        gw.guardarDiaCalendario.mockReset().mockRejectedValue(new BookingError(codigo, 'x', { status: 409 }))
        await falla(uc.guardarDia('s1', '2026-11-20', { cuposTotales: 10 }, { idempotencyKey: 'k' }))
        expect(gw.guardarDiaCalendario).toHaveBeenCalledTimes(1)
      }
      expect(esperar).not.toHaveBeenCalled()
    })
  })
})
