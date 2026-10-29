import { AuthError, CODIGOS_AUTH as C } from '../../domain/auth/errors.js'

/*
 * Adaptador HTTP del puerto AuthGateway: habla con iam-service a través del Gateway (Traefik, prefijo /api/iam).
 *
 * Rutas tal como las implementa services/iam-service en feature/iam-core:
 *   POST /api/iam/register   POST /api/iam/login   POST /api/iam/logout
 * La documentación (Plan §4.1, gateway/README) las nombra /api/iam/auth/{registro,login,recuperar}: se
 * dejan en RUTAS para ajustarlas en un solo lugar cuando se fije contracts/openapi/iam.yaml.
 * La recuperación de contraseña aún no existe en el servicio; sus rutas son PROPUESTAS.
 *
 * Errores del servicio: { detail, code, errores?: [{ campo, mensaje }] }
 */
export const RUTAS = Object.freeze({
  registro: '/register',
  login: '/login',
  logout: '/logout',
  recuperar: '/auth/recuperar', // propuesta (Plan §4.1)
  restablecer: '/auth/restablecer', // propuesta
})

export function createHttpAuthGateway({ baseUrl = '/api/iam', fetchFn = (...a) => fetch(...a), rutas = RUTAS } = {}) {
  async function http(method, path, { body, token } = {}) {
    const headers = { Accept: 'application/json' }
    if (body) headers['Content-Type'] = 'application/json'
    if (token) headers.Authorization = `Bearer ${token}`
    let res
    try { res = await fetchFn(`${baseUrl}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined }) }
    catch { throw new AuthError(C.SIN_CONEXION, 'No hay conexión con el servidor.') }
    if (res.status === 204) return null
    const data = await res.json().catch(() => null)
    if (!res.ok) throw aError(res.status, data)
    return data
  }

  const aError = (status, data) => {
    const campos = (data?.errores ?? []).map((e) => ({ campo: e.campo, mensaje: e.mensaje }))
    const code = data?.code ?? (status === 401 ? C.CREDENCIALES_INVALIDAS : status === 503 ? C.SERVICIO_NO_DISPONIBLE : 'ERROR')
    return new AuthError(code, data?.detail ?? 'No se pudo completar la operación.', { status, campos })
  }

  // La recuperación todavía no está en el servicio: 404/405/501 significa "aún no disponible", no "error"
  const propuesta = (p) => p.catch((e) => {
    if (e instanceof AuthError && [404, 405, 501].includes(e.status)) throw new AuthError(C.NO_IMPLEMENTADO, 'Esta función aún no está disponible.', { status: e.status })
    throw e
  })

  return {
    registrar: (datos) => http('POST', rutas.registro, { body: datos }),
    iniciarSesion: (credenciales) => http('POST', rutas.login, { body: credenciales }),
    cerrarSesion: (token) => http('POST', rutas.logout, { token }).then(() => undefined),
    solicitarRecuperacion: (email) => propuesta(http('POST', rutas.recuperar, { body: { email } }).then(() => ({ enviado: true }))),
    restablecerPassword: ({ token, password }) => propuesta(http('POST', rutas.restablecer, { body: { token, password } }).then(() => undefined)),
  }
}
