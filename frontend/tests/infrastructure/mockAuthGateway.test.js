import { beforeEach, describe, expect, it } from 'vitest'
import { CUENTA_DEMO, createMockAuthGateway } from '../../src/infrastructure/auth/mockAuthGateway.js'
import { createSessionStore } from '../../src/infrastructure/auth/sessionStore.js'
import { getToken, getUsuarioId } from '../../src/infrastructure/auth/tokenSession.js'
import { assertAuthGateway } from '../../src/application/auth/ports.js'
import { crearSesion } from '../../src/domain/auth/rules.js'

/* El simulado debe responder como iam-service: mismos códigos, mismo orden de comprobación, sin guardar contraseñas en claro. */
const T0 = new Date('2026-10-27T12:00:00Z')
const memoria = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), removeItem: (k) => m.delete(k), _m: m } }
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }
const datos = { email: 'nuevo@example.com', password: 'Tayrona2026', nombre_completo: 'Nuevo Usuario', rol: 'Turista', habeas_data_aceptado: true, es_mayor_de_edad: true }

let ahora, storage, gw
beforeEach(() => {
  ahora = new Date(T0)
  storage = memoria()
  gw = createMockAuthGateway({ storage, clock: { now: () => ahora }, delayMs: 0 })
})

it('implementa el puerto AuthGateway completo', () => expect(assertAuthGateway(gw)).toBe(gw))

describe('registrar', () => {
  it('crea una cuenta y devuelve solo datos públicos', async () => {
    const u = await gw.registrar({ ...datos, email: ' Nuevo@Example.COM ' })
    expect(u).toMatchObject({ email: 'nuevo@example.com', nombre_completo: 'Nuevo Usuario', rol: 'Turista', email_verificado: false })
    expect(Object.keys(u).sort()).toEqual(['creado_en', 'email', 'email_verificado', 'id', 'nombre_completo', 'rol'])
  })
  it('nunca guarda la contraseña en claro', async () => {
    await gw.registrar(datos)
    expect(JSON.stringify([...storage._m.values()])).not.toContain('Tayrona2026')
  })
  it('un correo repetido es EMAIL_EN_USO (409), sin importar mayúsculas', async () => {
    await gw.registrar(datos)
    expect(await falla(gw.registrar({ ...datos, email: 'NUEVO@example.com' }))).toMatchObject({ code: 'EMAIL_EN_USO', status: 409 })
  })
  it('la cuenta de demostración ya existe', async () => {
    expect((await falla(gw.registrar({ ...datos, email: CUENTA_DEMO.email }))).code).toBe('EMAIL_EN_USO')
  })
  it('responde con el primer error en el mismo orden que iam-service', async () => {
    const mal = { email: 'x', password: 'abc', nombre_completo: '', rol: 'Admin', habeas_data_aceptado: false, es_mayor_de_edad: false }
    expect((await falla(gw.registrar(mal))).code).toBe('HABEAS_DATA_REQUERIDO')
    expect((await falla(gw.registrar({ ...mal, habeas_data_aceptado: true }))).code).toBe('MAYORIA_DE_EDAD_REQUERIDA')
    expect((await falla(gw.registrar({ ...mal, habeas_data_aceptado: true, es_mayor_de_edad: true }))).code).toBe('ROL_NO_PERMITIDO')
    expect((await falla(gw.registrar({ ...mal, habeas_data_aceptado: true, es_mayor_de_edad: true, rol: 'Turista' }))).code).toBe('EMAIL_INVALIDO')
    expect((await falla(gw.registrar({ ...datos, password: 'abc' }))).code).toBe('PASSWORD_INVALIDA')
    expect((await falla(gw.registrar({ ...datos, nombre_completo: 'A' }))).code).toBe('NOMBRE_INVALIDO')
  })
  it('todos los rechazos de reglas de negocio son 422', async () => {
    expect((await falla(gw.registrar({ ...datos, habeas_data_aceptado: false }))).status).toBe(422)
  })
})

describe('iniciarSesion', () => {
  it('entrega access_token, expires_in de 15 min y el usuario', async () => {
    const r = await gw.iniciarSesion({ email: CUENTA_DEMO.email, password: CUENTA_DEMO.password })
    expect(r).toMatchObject({ token_type: 'bearer', expires_in: 900, usuario: { email: CUENTA_DEMO.email, rol: 'Turista' } })
    expect(r.access_token.split('.')).toHaveLength(3)
  })
  it('el token lleva sub, rol, jti y exp como el JWT del servicio', async () => {
    const r = await gw.iniciarSesion({ email: CUENTA_DEMO.email, password: CUENTA_DEMO.password })
    const claims = JSON.parse(atob(r.access_token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    expect(claims).toMatchObject({ sub: r.usuario.id, rol: 'Turista', iss: 'iam-service' })
    expect(claims.exp - claims.iat).toBe(900)
    expect(claims.jti).toBeTruthy()
  })
  it('ignora mayúsculas y espacios del correo', async () => {
    expect((await gw.iniciarSesion({ email: '  MARIA.PEREZ@example.com ', password: CUENTA_DEMO.password })).usuario.email).toBe(CUENTA_DEMO.email)
  })
  it('una contraseña mala o un correo inexistente dan la misma respuesta (no revela cuentas)', async () => {
    const a = await falla(gw.iniciarSesion({ email: CUENTA_DEMO.email, password: 'MalaClave1' }))
    const b = await falla(gw.iniciarSesion({ email: 'nadie@example.com', password: 'MalaClave1' }))
    expect(a).toMatchObject({ code: 'CREDENCIALES_INVALIDAS', status: 401 })
    expect({ code: b.code, status: b.status, message: b.message }).toEqual({ code: a.code, status: a.status, message: a.message })
  })
  it('se puede ingresar con la cuenta recién creada', async () => {
    await gw.registrar(datos)
    expect((await gw.iniciarSesion({ email: datos.email, password: datos.password })).usuario.nombre_completo).toBe('Nuevo Usuario')
  })
})

describe('cerrarSesion', () => {
  it('con token responde sin cuerpo; sin token es TOKEN_INVALIDO', async () => {
    await expect(gw.cerrarSesion('jwt')).resolves.toBeUndefined()
    expect((await falla(gw.cerrarSesion(''))).code).toBe('TOKEN_INVALIDO')
  })
})

describe('recuperación de contraseña', () => {
  const pedir = async (email) => gw.solicitarRecuperacion(email)

  it('responde igual exista o no la cuenta; solo cuando existe expone el enlace de demostración', async () => {
    const existe = await pedir(CUENTA_DEMO.email)
    const noExiste = await pedir('nadie@example.com')
    expect(existe.enviado).toBe(true)
    expect(noExiste).toEqual({ enviado: true })
    expect(existe.demo.token).toBeTruthy()
  })
  it('no expone el enlace si se desactiva (como en un entorno real)', async () => {
    const real = createMockAuthGateway({ storage, clock: { now: () => ahora }, delayMs: 0, exponerEnlaceDeRecuperacion: false })
    expect(await real.solicitarRecuperacion(CUENTA_DEMO.email)).toEqual({ enviado: true })
  })
  it('con el token se cambia la contraseña: la vieja deja de servir y la nueva sirve', async () => {
    const { demo } = await pedir(CUENTA_DEMO.email)
    await gw.restablecerPassword({ token: demo.token, password: 'NuevaClave77' })
    expect((await falla(gw.iniciarSesion({ email: CUENTA_DEMO.email, password: CUENTA_DEMO.password }))).code).toBe('CREDENCIALES_INVALIDAS')
    expect((await gw.iniciarSesion({ email: CUENTA_DEMO.email, password: 'NuevaClave77' })).usuario.email).toBe(CUENTA_DEMO.email)
  })
  it('un enlace sirve una sola vez', async () => {
    const { demo } = await pedir(CUENTA_DEMO.email)
    await gw.restablecerPassword({ token: demo.token, password: 'NuevaClave77' })
    expect((await falla(gw.restablecerPassword({ token: demo.token, password: 'OtraClave88' }))).code).toBe('TOKEN_INVALIDO')
  })
  it('el enlace vence a los 30 minutos', async () => {
    const { demo } = await pedir(CUENTA_DEMO.email)
    ahora = new Date(T0.getTime() + 31 * 60_000)
    expect((await falla(gw.restablecerPassword({ token: demo.token, password: 'NuevaClave77' }))).code).toBe('TOKEN_INVALIDO')
  })
  it('un token inventado es TOKEN_INVALIDO y una contraseña débil es PASSWORD_INVALIDA', async () => {
    expect(await falla(gw.restablecerPassword({ token: 'inventado', password: 'NuevaClave77' }))).toMatchObject({ code: 'TOKEN_INVALIDO', status: 400 })
    const { demo } = await pedir(CUENTA_DEMO.email)
    expect(await falla(gw.restablecerPassword({ token: demo.token, password: 'corta' }))).toMatchObject({ code: 'PASSWORD_INVALIDA', status: 422 })
  })
})

describe('almacén de sesión y token para el resto de módulos', () => {
  const resp = { access_token: 'jwt-9', expires_in: 900, usuario: { id: 'u9', email: 'a@b.co' } }

  it('guarda, recupera y borra la sesión', () => {
    const store = createSessionStore({ storage })
    expect(store.load()).toBeNull()
    store.save(crearSesion(resp, T0))
    expect(store.load()).toMatchObject({ token: 'jwt-9', usuario: { id: 'u9' } })
    store.clear()
    expect(store.load()).toBeNull()
  })
  it('un valor corrupto o un almacenamiento ausente no rompen nada', () => {
    storage.setItem('session.v1', '{no es json')
    expect(createSessionStore({ storage }).load()).toBeNull()
    const sin = createSessionStore({ storage: { getItem() { throw new Error('bloqueado') }, setItem() { throw new Error('bloqueado') }, removeItem() { throw new Error('bloqueado') } } })
    expect(() => { sin.save({}); sin.clear() }).not.toThrow()
    expect(sin.load()).toBeNull()
  })
  it('getToken entrega el JWT solo mientras la sesión está vigente', () => {
    const store = createSessionStore({ storage })
    expect(getToken(store, T0)).toBeNull()
    store.save(crearSesion(resp, T0))
    expect(getToken(store, T0)).toBe('jwt-9')
    expect(getToken(store, new Date(T0.getTime() + 880_000))).toBeNull() // dentro del margen de 30 s
    expect(getUsuarioId(store)).toBe('u9')
  })
})
