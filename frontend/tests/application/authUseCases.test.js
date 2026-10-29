import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthError } from '../../src/domain/auth/errors.js'
import { createAuthUseCases } from '../../src/application/auth/useCases.js'
import { assertAuthGateway, AUTH_GATEWAY_METHODS } from '../../src/application/auth/ports.js'

const AHORA = new Date('2026-10-27T12:00:00Z')
const usuario = { id: 'u1', email: 'maria.perez@example.com', nombre_completo: 'María Pérez', rol: 'Turista' }
const registro = { email: ' Maria.Perez@Example.com ', password: 'Tayrona2026', nombre: ' María Pérez ', rol: 'Turista', habeasDataAceptado: true, esMayorDeEdad: true }

let gateway, store, localData, clock, uc, guardada
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }

beforeEach(() => {
  guardada = null
  gateway = {
    registrar: vi.fn(async () => usuario),
    iniciarSesion: vi.fn(async () => ({ access_token: 'jwt-1', token_type: 'bearer', expires_in: 900, usuario })),
    cerrarSesion: vi.fn(async () => {}),
    solicitarRecuperacion: vi.fn(async () => ({ enviado: true })),
    restablecerPassword: vi.fn(async () => {}),
  }
  store = { load: vi.fn(() => guardada), save: vi.fn((s) => { guardada = s }), clear: vi.fn(() => { guardada = null }) }
  localData = { clearAll: vi.fn(async () => {}) }
  clock = { now: () => AHORA }
  uc = createAuthUseCases({ gateway, store, localData, clock })
})

describe('puerto AuthGateway', () => {
  it('rechaza un adaptador incompleto indicando qué le falta', () => {
    expect(() => assertAuthGateway({ registrar() {} })).toThrow(/iniciarSesion/)
    expect(() => createAuthUseCases({ gateway: {}, store, localData, clock })).toThrow(TypeError)
  })
  it('acepta uno completo', () => {
    const g = Object.fromEntries(AUTH_GATEWAY_METHODS.map((m) => [m, () => {}]))
    expect(assertAuthGateway(g)).toBe(g)
  })
})

describe('iniciarSesion (UC2)', () => {
  it('normaliza el correo, guarda la sesión con su vencimiento y la devuelve', async () => {
    const s = await uc.iniciarSesion({ email: '  MARIA.PEREZ@example.com ', password: 'Tayrona2026' })
    expect(gateway.iniciarSesion).toHaveBeenCalledWith({ email: 'maria.perez@example.com', password: 'Tayrona2026' })
    expect(s).toEqual({ token: 'jwt-1', usuario, expiraEn: AHORA.getTime() + 900_000 })
    expect(store.save).toHaveBeenCalledWith(s)
  })
  it('sin correo o contraseña no llama al servidor', async () => {
    const e = await falla(uc.iniciarSesion({ email: '', password: '' }))
    expect(e).toMatchObject({ code: 'VALIDACION' })
    expect(e.campos.map((c) => c.campo)).toEqual(['email', 'password'])
    expect(gateway.iniciarSesion).not.toHaveBeenCalled()
  })
  it('las credenciales incorrectas se propagan y no se guarda nada', async () => {
    gateway.iniciarSesion.mockRejectedValue(new AuthError('CREDENCIALES_INVALIDAS', 'Correo o contraseña incorrectos.', { status: 401 }))
    const e = await falla(uc.iniciarSesion({ email: 'a@b.co', password: 'mala' }))
    expect(e).toMatchObject({ code: 'CREDENCIALES_INVALIDAS', status: 401 })
    expect(store.save).not.toHaveBeenCalled()
  })
})

describe('estado de la sesión', () => {
  it('sin sesión: no autenticado, sin usuario y sin vencer', () => {
    expect(uc.estado()).toEqual({ autenticado: false, usuario: null, expirada: false })
    expect(uc.expiraEn()).toBeNull()
  })
  it('con token vigente está autenticado y expiraEn incluye el margen de 30 s', async () => {
    await uc.iniciarSesion({ email: 'a@b.co', password: 'x' })
    expect(uc.estado()).toEqual({ autenticado: true, usuario, expirada: false })
    expect(uc.expiraEn()).toBe(AHORA.getTime() + 900_000 - 30_000)
  })
  it('con el token vencido ya no está autenticado, pero recuerda al usuario y marca expirada', async () => {
    await uc.iniciarSesion({ email: 'a@b.co', password: 'x' })
    const tarde = createAuthUseCases({ gateway, store, localData, clock: { now: () => new Date(AHORA.getTime() + 901_000) } })
    expect(tarde.estado()).toEqual({ autenticado: false, usuario, expirada: true })
    expect(tarde.expiraEn()).toBeNull()
  })
  it('invalidarSesion (401 del backend) borra el token pero conserva al usuario', async () => {
    await uc.iniciarSesion({ email: 'a@b.co', password: 'x' })
    uc.invalidarSesion()
    expect(uc.estado()).toEqual({ autenticado: false, usuario, expirada: true })
    expect(guardada.token).toBeNull()
  })
  it('invalidarSesion sin sesión no hace nada', () => {
    uc.invalidarSesion()
    expect(store.save).not.toHaveBeenCalled()
  })
})

describe('registrar (UC1 + UC6)', () => {
  it('valida todo antes de llamar y devuelve los errores por campo', async () => {
    const e = await falla(uc.registrar({ email: 'x', password: 'abc', nombre: '', rol: 'Admin', habeasDataAceptado: false, esMayorDeEdad: false }))
    expect(e).toMatchObject({ code: 'VALIDACION', status: 422 })
    expect(e.campos.map((c) => c.campo).sort()).toEqual(['email', 'habeasData', 'mayorDeEdad', 'nombre', 'password', 'rol'])
    expect(gateway.registrar).not.toHaveBeenCalled()
  })
  it('envía el cuerpo del contrato de iam-service con el correo normalizado y el nombre recortado', async () => {
    await uc.registrar(registro)
    expect(gateway.registrar).toHaveBeenCalledWith({
      email: 'maria.perez@example.com', password: 'Tayrona2026', nombre_completo: 'María Pérez', rol: 'Turista',
      habeas_data_aceptado: true, es_mayor_de_edad: true,
    })
  })
  it('tras registrar inicia sesión automáticamente (el servidor no lo hace)', async () => {
    const r = await uc.registrar(registro)
    expect(r).toMatchObject({ usuario, sesionIniciada: true })
    expect(r.sesion.token).toBe('jwt-1')
    expect(uc.estado().autenticado).toBe(true)
  })
  it('si la cuenta se crea pero el ingreso automático falla, lo informa sin perder la cuenta', async () => {
    gateway.iniciarSesion.mockRejectedValue(new AuthError('SIN_CONEXION', 'No hay conexión.'))
    const r = await uc.registrar(registro)
    expect(r).toEqual({ usuario, sesion: null, sesionIniciada: false })
    expect(uc.estado().autenticado).toBe(false)
  })
  it('el correo en uso se propaga como EMAIL_EN_USO', async () => {
    gateway.registrar.mockRejectedValue(new AuthError('EMAIL_EN_USO', 'Ya existe una cuenta.', { status: 409 }))
    expect(await falla(uc.registrar(registro))).toMatchObject({ code: 'EMAIL_EN_USO', status: 409 })
    expect(gateway.iniciarSesion).not.toHaveBeenCalled()
  })
})

describe('cerrarSesion', () => {
  it('revoca el token en el servidor, borra la sesión y lo guardado en el dispositivo', async () => {
    await uc.iniciarSesion({ email: 'a@b.co', password: 'x' })
    await uc.cerrarSesion()
    expect(gateway.cerrarSesion).toHaveBeenCalledWith('jwt-1')
    expect(guardada).toBeNull()
    expect(localData.clearAll).toHaveBeenCalledTimes(1)
  })
  it('sin red igual cierra la sesión en el dispositivo', async () => {
    await uc.iniciarSesion({ email: 'a@b.co', password: 'x' })
    gateway.cerrarSesion.mockRejectedValue(new AuthError('SIN_CONEXION', 'No hay conexión.'))
    await uc.cerrarSesion()
    expect(guardada).toBeNull()
    expect(localData.clearAll).toHaveBeenCalled()
  })
  it('con el token ya vencido no llama al servidor, pero sí limpia', async () => {
    await uc.iniciarSesion({ email: 'a@b.co', password: 'x' })
    const tarde = createAuthUseCases({ gateway, store, localData, clock: { now: () => new Date(AHORA.getTime() + 901_000) } })
    await tarde.cerrarSesion()
    expect(gateway.cerrarSesion).not.toHaveBeenCalled()
    expect(guardada).toBeNull()
  })
  it('un fallo al borrar los datos locales no impide cerrar la sesión', async () => {
    await uc.iniciarSesion({ email: 'a@b.co', password: 'x' })
    localData.clearAll.mockRejectedValue(new Error('IndexedDB'))
    await expect(uc.cerrarSesion()).resolves.toBeUndefined()
    expect(guardada).toBeNull()
  })
})

describe('recuperar contraseña (UC3)', () => {
  it('rechaza un correo mal formado sin llamar al servidor', async () => {
    expect((await falla(uc.solicitarRecuperacion('no-es-correo'))).code).toBe('VALIDACION')
    expect(gateway.solicitarRecuperacion).not.toHaveBeenCalled()
  })
  it('pide el enlace con el correo normalizado', async () => {
    await uc.solicitarRecuperacion(' Maria.Perez@Example.com ')
    expect(gateway.solicitarRecuperacion).toHaveBeenCalledWith('maria.perez@example.com')
  })
  it('restablecer sin token es TOKEN_INVALIDO y no llama al servidor', async () => {
    expect((await falla(uc.restablecerPassword({ token: '', password: 'NuevaClave77', confirmacion: 'NuevaClave77' }))).code).toBe('TOKEN_INVALIDO')
    expect(gateway.restablecerPassword).not.toHaveBeenCalled()
  })
  it('valida la política y la confirmación antes de llamar', async () => {
    expect((await falla(uc.restablecerPassword({ token: 't', password: 'corta', confirmacion: 'corta' }))).campos[0].campo).toBe('password')
    expect((await falla(uc.restablecerPassword({ token: 't', password: 'NuevaClave77', confirmacion: 'x' }))).campos[0].campo).toBe('confirmacion')
    expect(gateway.restablecerPassword).not.toHaveBeenCalled()
  })
  it('envía el token y la nueva contraseña (sin la confirmación)', async () => {
    await uc.restablecerPassword({ token: 'tok', password: 'NuevaClave77', confirmacion: 'NuevaClave77' })
    expect(gateway.restablecerPassword).toHaveBeenCalledWith({ token: 'tok', password: 'NuevaClave77' })
  })
})
