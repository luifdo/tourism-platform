import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthError } from '../../src/domain/auth/errors.js'
import { createAuthUseCases } from '../../src/application/auth/useCases.js'

/*
 * Renovación del access token con el refresh token (iam-service, sección "Sesión y refresh token"):
 * cada renovación entrega un refresh NUEVO y el anterior muere; usarlo otra vez se toma como robo y revoca la sesión.
 */
const T0 = new Date('2026-11-12T12:00:00Z')
const usuario = { id: 'u1', email: 'a@b.co', nombre_completo: 'A B', rol: 'Turista' }
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }
const respuesta = (n) => ({ access_token: `a${n}`, token_type: 'bearer', expires_in: 900, refresh_token: `r${n}`, refresh_expires_in: 604_800, usuario })

/** Un "iam-service" que rota los refresh y revoca la sesión si se reutiliza uno. */
function servicioIam() {
  let n = 1
  const estado = { vigente: 'r1', revocada: false, llamadas: 0 }
  return {
    estado,
    gateway: {
      renovar: vi.fn(async (refresh) => {
        estado.llamadas += 1
        await new Promise((r) => setTimeout(r, 5))
        if (estado.revocada || refresh !== estado.vigente) { estado.revocada = true; throw new AuthError('TOKEN_INVALIDO', 'El token no es válido.', { status: 401 }) }
        n += 1; estado.vigente = `r${n}`
        return respuesta(n)
      }),
    },
  }
}
const almacen = (inicial = null) => { let s = inicial; return { load: vi.fn(() => s), save: vi.fn((x) => { s = x }), clear: vi.fn(() => { s = null }) } }
/** Exclusión mutua, como Web Locks: una función a la vez, compartida entre "pestañas". */
const candado = () => { let cola = Promise.resolve(); return { run: (fn) => { const p = cola.then(fn, fn); cola = p.catch(() => {}); return p } } }
const sesionInicial = (n = 1, desde = T0) => ({ token: `a${n}`, usuario, expiraEn: desde.getTime() + 900_000, refreshToken: `r${n}`, refreshExpiraEn: desde.getTime() + 604_800_000 })

let ahora, iam, store, uc
const crear = (opts = {}) => createAuthUseCases({
  gateway: { registrar: vi.fn(), iniciarSesion: vi.fn(), cerrarSesion: vi.fn(async () => {}), solicitarRecuperacion: vi.fn(), restablecerPassword: vi.fn(), ...iam.gateway },
  store, localData: { clearAll: vi.fn(async () => {}) }, clock: { now: () => ahora }, ...opts,
})
const pasar = (ms) => { ahora = new Date(ahora.getTime() + ms) }

beforeEach(() => {
  ahora = new Date(T0)
  iam = servicioIam()
  store = almacen(sesionInicial())
  uc = crear()
})

describe('obtenerToken', () => {
  it('con el access vigente lo entrega sin llamar al servicio', async () => {
    expect(await uc.obtenerToken()).toBe('a1')
    expect(iam.gateway.renovar).not.toHaveBeenCalled()
  })

  it('con el access vencido y el refresh vigente renueva y entrega el nuevo', async () => {
    pasar(900_000)
    expect(await uc.obtenerToken()).toBe('a2')
    expect(iam.gateway.renovar).toHaveBeenCalledWith('r1')
    expect(store.load()).toMatchObject({ token: 'a2', refreshToken: 'r2' }) // guarda los DOS nuevos
  })

  it('sin sesión, o con el refresh también vencido, entrega null', async () => {
    expect(await crear().obtenerToken()).toBe('a1')
    store = almacen(null)
    expect(await crear().obtenerToken()).toBeNull()
    store = almacen(sesionInicial())
    pasar(8 * 24 * 3600_000)
    expect(await crear().obtenerToken()).toBeNull()
    expect(iam.gateway.renovar).not.toHaveBeenCalled()
  })

  it('una sesión guardada antes del refresh (sin refresh_token) no renueva: vence a los 15 min', async () => {
    store = almacen({ token: 'viejo', usuario, expiraEn: T0.getTime() + 900_000 })
    uc = crear()
    expect(await uc.obtenerToken()).toBe('viejo')
    pasar(900_000)
    expect(await uc.obtenerToken()).toBeNull()
    expect(iam.gateway.renovar).not.toHaveBeenCalled()
  })

  it('si renovar falla por algo pasajero devuelve el token que haya y NO pierde la sesión', async () => {
    pasar(900_000)
    iam.gateway.renovar.mockRejectedValueOnce(new AuthError('SERVICIO_NO_DISPONIBLE', 'iam no responde', { status: 503 }))
    expect(await uc.obtenerToken()).toBe('a1') // que decida el servidor
    expect(store.load()).toMatchObject({ refreshToken: 'r1' })
    expect(await uc.obtenerToken()).toBe('a2') // y al volver iam, renueva
  })
})

describe('renovarSesion', () => {
  it('una sola renovación aunque lleguen muchas peticiones a la vez en la misma pestaña', async () => {
    pasar(900_000)
    const tokens = await Promise.all(Array.from({ length: 8 }, () => uc.obtenerToken()))
    expect(iam.estado.llamadas).toBe(1)
    expect(new Set(tokens)).toEqual(new Set(['a2']))
    expect(iam.estado.revocada).toBe(false)
  })

  it('dos pestañas a la vez: el candado deja pasar a una y la otra relee la sesión ya renovada (no se toma por robo)', async () => {
    const lock = candado()
    const pestanaA = crear({ lock })
    const pestanaB = crear({ lock }) // misma sesión guardada (localStorage), otro estado en memoria
    pasar(900_000)
    const [ta, tb] = await Promise.all([pestanaA.obtenerToken(), pestanaB.obtenerToken()])
    expect(iam.estado.llamadas).toBe(1)
    expect(iam.estado.revocada).toBe(false)
    expect([ta, tb]).toEqual(['a2', 'a2'])
  })

  it('sin candado entre pestañas, el servicio vería el refresh reutilizado: eso es lo que el candado evita', async () => {
    const A = crear() // cada una con su propio candado: no se coordinan
    const B = crear()
    pasar(900_000)
    await Promise.allSettled([A.obtenerToken(), B.obtenerToken()])
    expect(iam.estado.revocada).toBe(true)
  })

  it('tras un 401 con el token que tenía: si otra pestaña ya renovó, usa el nuevo sin renovar otra vez', async () => {
    await uc.renovarSesion({ tokenFallido: 'a1' }) // renueva: a1 falló
    const r = await crear().renovarSesion({ tokenFallido: 'a1' }) // otra petición que también usó a1
    expect(r.token).toBe('a2')
    expect(iam.estado.llamadas).toBe(1)
  })

  it('tras un 401 con el token vigente renueva de todos modos (revocado en el servidor, reloj desajustado)', async () => {
    const r = await uc.renovarSesion({ tokenFallido: 'a1' })
    expect(r.token).toBe('a2')
    expect(iam.estado.llamadas).toBe(1)
  })

  it('si el servicio responde TOKEN_INVALIDO la sesión queda invalidada, sin refresh, y devuelve null', async () => {
    iam.estado.vigente = 'otro' // el refresh guardado ya no sirve (revocado, o ya usado)
    expect(await uc.renovarSesion({ tokenFallido: 'a1' })).toBeNull()
    expect(store.load()).toEqual({ token: null, usuario, expiraEn: 0, refreshToken: null, refreshExpiraEn: 0 })
    expect(uc.estado()).toEqual({ autenticado: false, usuario, expirada: true })
    expect(await uc.renovarSesion()).toBeNull() // y no vuelve a insistir con un refresh muerto
    expect(iam.estado.llamadas).toBe(1)
  })

  it('un fallo pasajero se propaga y deja la sesión intacta para reintentar', async () => {
    for (const e of [new AuthError('SIN_CONEXION', 'sin red'), new AuthError('SERVICIO_NO_DISPONIBLE', '503', { status: 503 }), new AuthError('VALIDACION', '422', { status: 422 })]) {
      iam.gateway.renovar.mockRejectedValueOnce(e)
      expect((await falla(uc.renovarSesion({ tokenFallido: 'a1' }))).code).toBe(e.code)
      expect(store.load()).toMatchObject({ token: 'a1', refreshToken: 'r1' })
    }
    expect((await uc.renovarSesion({ tokenFallido: 'a1' })).token).toBe('a2')
  })

  it('después de fallar, la siguiente renovación vuelve a intentarlo (no queda atascada)', async () => {
    iam.gateway.renovar.mockRejectedValueOnce(new AuthError('SIN_CONEXION', 'x'))
    await falla(uc.renovarSesion({ tokenFallido: 'a1' }))
    expect((await uc.renovarSesion({ tokenFallido: 'a1' })).token).toBe('a2')
  })
})

describe('estado, expiraEn y renovarEn con refresh', () => {
  it('con el access vencido pero renovable sigue autenticado (no se pide ingresar)', () => {
    pasar(900_000)
    expect(uc.estado()).toEqual({ autenticado: true, usuario, expirada: false })
  })

  it('pasados los 7 días sin renovar, la sesión vence', () => {
    pasar(8 * 24 * 3600_000)
    expect(uc.estado()).toEqual({ autenticado: false, usuario, expirada: true })
  })

  it('renovarEn: 30 s antes de que venza el access; ya mismo si venció; null si no hay cómo renovar', () => {
    expect(uc.renovarEn()).toBe(T0.getTime() + 900_000 - 30_000)
    pasar(900_000)
    expect(uc.renovarEn()).toBe(ahora.getTime())
    pasar(8 * 24 * 3600_000)
    expect(uc.renovarEn()).toBeNull()
  })

  it('expiraEn solo aplica a sesiones sin refresh (las demás se renuevan)', () => {
    expect(uc.expiraEn()).toBeNull()
    store = almacen({ token: 'viejo', usuario, expiraEn: T0.getTime() + 900_000 })
    expect(crear().expiraEn()).toBe(T0.getTime() + 900_000 - 30_000)
  })
})

describe('cerrarSesion con refresh', () => {
  it('si el access venció, renueva antes para poder revocar la sesión en el servidor', async () => {
    const g = { cerrarSesion: vi.fn(async () => {}) }
    uc = crear({ gateway: { registrar: vi.fn(), iniciarSesion: vi.fn(), solicitarRecuperacion: vi.fn(), restablecerPassword: vi.fn(), ...iam.gateway, ...g } })
    pasar(900_000)
    await uc.cerrarSesion()
    expect(g.cerrarSesion).toHaveBeenCalledWith('a2')
    expect(store.load()).toBeNull()
  })

  it('si no se puede renovar, igual se cierra en el dispositivo', async () => {
    iam.estado.vigente = 'otro'
    pasar(900_000)
    await expect(uc.cerrarSesion()).resolves.toBeUndefined()
    expect(store.load()).toBeNull()
  })
})
