import { describe, expect, it, vi } from 'vitest'
import { createHttpAuthGateway, RUTAS } from '../../src/infrastructure/auth/httpAuthGateway.js'
import { assertAuthGateway } from '../../src/application/auth/ports.js'
import { AuthError } from '../../src/domain/auth/errors.js'

/*
 * Estas pruebas fijan el contrato REAL de iam-service (rama feature/iam-core): rutas /api/iam/register|login|logout
 * y errores { detail, code, errores? }. Si el servicio cambia, fallarán aquí y no en producción.
 */
const respuesta = (cuerpo, status = 200) => ({
  ok: status < 400, status, json: async () => { if (cuerpo === undefined) throw new Error('sin cuerpo'); return cuerpo },
})
const crear = (fetchFn) => createHttpAuthGateway({ baseUrl: '/api/iam', fetchFn })
const falla = async (p) => { try { await p } catch (e) { return e } throw new Error('se esperaba un error') }

describe('adaptador HTTP de autenticación (iam-service)', () => {
  it('implementa el puerto AuthGateway completo', () => expect(assertAuthGateway(crear(vi.fn()))).toBeTruthy())

  it('las rutas son las que implementa el servicio', () => {
    expect(RUTAS).toMatchObject({ registro: '/register', login: '/login', logout: '/logout' })
  })

  it('registrar: POST /api/iam/register con el cuerpo del servicio y devuelve el usuario público', async () => {
    const publico = { id: 'u1', email: 'a@b.co', nombre_completo: 'A B', rol: 'Turista', email_verificado: false, creado_en: '2026-10-27T00:00:00Z' }
    const fetchFn = vi.fn(async () => respuesta(publico, 201))
    const cuerpo = { email: 'a@b.co', password: 'Tayrona2026', nombre_completo: 'A B', rol: 'Turista', habeas_data_aceptado: true, es_mayor_de_edad: true }
    expect(await crear(fetchFn).registrar(cuerpo)).toEqual(publico)
    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('/api/iam/register')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual(cuerpo)
    expect(init.headers['Content-Type']).toBe('application/json')
  })

  it('iniciarSesión: POST /api/iam/login y devuelve access_token, expires_in y usuario', async () => {
    const login = { access_token: 'jwt', token_type: 'bearer', expires_in: 900, usuario: { id: 'u1' } }
    const fetchFn = vi.fn(async () => respuesta(login))
    expect(await crear(fetchFn).iniciarSesion({ email: 'a@b.co', password: 'x' })).toEqual(login)
    expect(fetchFn.mock.calls[0][0]).toBe('/api/iam/login')
    expect(JSON.parse(fetchFn.mock.calls[0][1].body)).toEqual({ email: 'a@b.co', password: 'x' })
  })

  it('cerrarSesión: POST /api/iam/logout con el Bearer; el 204 no trae cuerpo', async () => {
    const fetchFn = vi.fn(async () => respuesta(undefined, 204))
    await expect(crear(fetchFn).cerrarSesion('jwt-1')).resolves.toBeUndefined()
    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('/api/iam/logout')
    expect(init.headers.Authorization).toBe('Bearer jwt-1')
    expect(init.body).toBeUndefined()
  })

  it('login con credenciales malas: 401 CREDENCIALES_INVALIDAS con el mensaje del servidor', async () => {
    const fetchFn = vi.fn(async () => respuesta({ detail: 'Correo o contraseña incorrectos.', code: 'CREDENCIALES_INVALIDAS' }, 401))
    const e = await falla(crear(fetchFn).iniciarSesion({ email: 'a@b.co', password: 'mala' }))
    expect(e).toBeInstanceOf(AuthError)
    expect(e).toMatchObject({ code: 'CREDENCIALES_INVALIDAS', status: 401, message: 'Correo o contraseña incorrectos.' })
  })

  it('cuenta inactiva (403) y correo en uso (409) conservan su código', async () => {
    const a = await falla(crear(vi.fn(async () => respuesta({ detail: 'x', code: 'CUENTA_INACTIVA' }, 403))).iniciarSesion({}))
    expect(a).toMatchObject({ code: 'CUENTA_INACTIVA', status: 403 })
    const b = await falla(crear(vi.fn(async () => respuesta({ detail: 'x', code: 'EMAIL_EN_USO' }, 409))).registrar({}))
    expect(b).toMatchObject({ code: 'EMAIL_EN_USO', status: 409 })
  })

  it('un 422 VALIDACION trae la lista de campos', async () => {
    const cuerpo = { detail: 'Los datos enviados no son válidos.', code: 'VALIDACION', errores: [{ campo: 'email', mensaje: 'value is not a valid email address' }, { campo: 'rol', mensaje: 'Input should be Turista or Prestador' }] }
    const e = await falla(crear(vi.fn(async () => respuesta(cuerpo, 422))).registrar({}))
    expect(e).toMatchObject({ code: 'VALIDACION', status: 422 })
    expect(e.campos).toEqual([{ campo: 'email', mensaje: 'value is not a valid email address' }, { campo: 'rol', mensaje: 'Input should be Turista or Prestador' }])
  })

  it('los códigos de regla de negocio (422) llegan tal cual', async () => {
    for (const code of ['HABEAS_DATA_REQUERIDO', 'MAYORIA_DE_EDAD_REQUERIDA', 'PASSWORD_INVALIDA', 'NOMBRE_INVALIDO']) {
      const e = await falla(crear(vi.fn(async () => respuesta({ detail: 'm', code }, 422))).registrar({}))
      expect(e.code, code).toBe(code)
    }
  })

  it('un 401 o 503 sin cuerpo se interpretan por su estado', async () => {
    expect((await falla(crear(vi.fn(async () => respuesta(undefined, 401))).iniciarSesion({}))).code).toBe('CREDENCIALES_INVALIDAS')
    expect((await falla(crear(vi.fn(async () => respuesta(undefined, 503))).iniciarSesion({}))).code).toBe('SERVICIO_NO_DISPONIBLE')
  })

  it('un fallo de red es SIN_CONEXION', async () => {
    const e = await falla(crear(vi.fn(async () => { throw new TypeError('Failed to fetch') })).iniciarSesion({}))
    expect(e).toMatchObject({ code: 'SIN_CONEXION', status: 0 })
  })

  it('logout con token revocado: 401 TOKEN_INVALIDO', async () => {
    const e = await falla(crear(vi.fn(async () => respuesta({ detail: 'x', code: 'TOKEN_INVALIDO' }, 401))).cerrarSesion('viejo'))
    expect(e.code).toBe('TOKEN_INVALIDO')
  })

  describe('recuperación de contraseña (rutas propuestas: aún no existen en el servicio)', () => {
    it('si el servicio no la tiene (404) responde NO_IMPLEMENTADO en vez de un error genérico', async () => {
      const fetchFn = vi.fn(async () => respuesta({ detail: 'Not Found' }, 404))
      expect((await falla(crear(fetchFn).solicitarRecuperacion('a@b.co'))).code).toBe('NO_IMPLEMENTADO')
      expect((await falla(crear(fetchFn).restablecerPassword({ token: 't', password: 'NuevaClave77' }))).code).toBe('NO_IMPLEMENTADO')
    })
    it('cuando exista, pide el enlace con solo el correo y no revela si la cuenta existe', async () => {
      const fetchFn = vi.fn(async () => respuesta(undefined, 202))
      expect(await crear(fetchFn).solicitarRecuperacion('a@b.co')).toEqual({ enviado: true })
      expect(fetchFn.mock.calls[0][0]).toBe('/api/iam/auth/recuperar')
      expect(JSON.parse(fetchFn.mock.calls[0][1].body)).toEqual({ email: 'a@b.co' })
    })
    it('el token inválido (400) se conserva como TOKEN_INVALIDO', async () => {
      const e = await falla(crear(vi.fn(async () => respuesta({ detail: 'x', code: 'TOKEN_INVALIDO' }, 400))).restablecerPassword({ token: 't', password: 'NuevaClave77' }))
      expect(e.code).toBe('TOKEN_INVALIDO')
    })
  })
})
