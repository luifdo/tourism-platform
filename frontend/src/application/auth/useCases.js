import { AuthError, CODIGOS_AUTH } from '../../domain/auth/errors.js'
import {
  MARGEN_EXPIRACION_MS, crearSesion, emailValido, normalizarEmail, puedeRenovar, sesionActiva, sesionVigente, validarLogin, validarNuevaPassword, validarRegistro, vencerSesion,
} from '../../domain/auth/rules.js'
import { assertAuthGateway } from './ports.js'

/*
 * Casos de uso de autenticación (UC1 registro, UC2 inicio de sesión, UC3 recuperar contraseña,
 * UC6 consentimiento de datos). Sin Vue, sin HTTP, sin almacenamiento: todo entra por los puertos.
 */
export function createAuthUseCases({ gateway, store, localData, clock, lock = { run: (fn) => fn() } }) {
  assertAuthGateway(gateway)
  const ahora = () => clock.now()
  let renovando = null // la renovación en curso en esta pestaña: las demás peticiones esperan la misma

  const rechazar = (errores, mensaje = 'Los datos enviados no son válidos.') => {
    throw new AuthError(CODIGOS_AUTH.VALIDACION, mensaje, { status: 422, campos: errores })
  }

  /** UC2 */
  async function iniciarSesion({ email, password }) {
    const errores = validarLogin({ email, password })
    if (errores.length) rechazar(errores)
    const respuesta = await gateway.iniciarSesion({ email: normalizarEmail(email), password })
    const sesion = crearSesion(respuesta, ahora())
    store.save(sesion)
    return sesion
  }

  /**
   * Cambia el refresh token por un access token nuevo (y un refresh nuevo). A la vez solo una: el servicio toma
   * como robo usar dos veces el mismo refresh y cierra la sesión. Dentro del candado (que vale también entre
   * pestañas) se relee la sesión: si otra pestaña ya renovó, se usa lo suyo en vez de renovar otra vez.
   *
   * `tokenFallido`: el access token con el que el servidor respondió 401. Si lo guardado ya es otro, alguien ya renovó.
   * Devuelve la sesión vigente, o null si ya no se puede seguir (el refresh venció, se revocó o se reutilizó; la
   * sesión queda invalidada y hay que ingresar de nuevo). Un fallo pasajero (sin red, 503) se propaga SIN tocar la
   * sesión: el refresh sigue sirviendo y se reintenta más tarde.
   */
  function renovarSesion({ tokenFallido = null } = {}) {
    if (renovando) return renovando
    renovando = lock.run(async () => {
      const s = store.load()
      if (!puedeRenovar(s, ahora())) return sesionVigente(s, ahora()) ? s : null
      if (sesionVigente(s, ahora()) && s.token !== tokenFallido) return s // otra pestaña (o petición) ya renovó
      try {
        const sesion = crearSesion(await gateway.renovar(s.refreshToken), ahora())
        store.save(sesion)
        return sesion
      } catch (e) {
        if (e instanceof AuthError && e.code === CODIGOS_AUTH.TOKEN_INVALIDO) {
          store.save(vencerSesion(s)) // el refresh no sirve: se conserva quién era para pedir ingresar de nuevo
          return null
        }
        throw e
      }
    }).finally(() => { renovando = null })
    return renovando
  }

  /** El access token a usar ahora; si venció y hay refresh, lo renueva. null si no hay sesión o ya no se puede seguir. */
  async function obtenerToken() {
    const s = store.load()
    if (sesionVigente(s, ahora())) return s.token
    if (!puedeRenovar(s, ahora())) return null
    try { return (await renovarSesion())?.token ?? null } catch { return s.token ?? null } // fallo pasajero: que decida el servidor
  }

  return {
    /** Estado actual: ¿sigue dentro? (con el access token vigente, o vencido pero renovable), ¿quién era?, ¿venció? */
    estado() {
      const s = store.load()
      const autenticado = sesionActiva(s, ahora())
      return { autenticado, usuario: s?.usuario ?? null, expirada: !!s && !autenticado }
    },

    /**
     * Momento (ms) en que la sesión deja de servir si NO se puede renovar (con el margen de seguridad), o null.
     * Sirve para reflejar el vencimiento sin esperar a la próxima petición.
     */
    expiraEn() {
      const s = store.load()
      return !puedeRenovar(s, ahora()) && sesionVigente(s, ahora()) ? s.expiraEn - MARGEN_EXPIRACION_MS : null
    },

    /**
     * Momento (ms) en que conviene renovar: cuando el access token está por vencer (ya, si venció). null si no hay
     * sesión que renovar.
     */
    renovarEn() {
      const s = store.load()
      if (!puedeRenovar(s, ahora())) return null
      return sesionVigente(s, ahora()) ? s.expiraEn - MARGEN_EXPIRACION_MS : ahora().getTime()
    },

    renovarSesion,
    obtenerToken,

    iniciarSesion,

    /** UC1 + UC6: registra y, si sale bien, inicia sesión (el servidor no lo hace por sí solo). */
    async registrar({ email, password, nombre, rol, habeasDataAceptado, esMayorDeEdad }) {
      const errores = validarRegistro({ email, password, nombre, rol, habeasDataAceptado, esMayorDeEdad })
      if (errores.length) rechazar(errores)
      const usuario = await gateway.registrar({
        email: normalizarEmail(email),
        password,
        nombre_completo: nombre.trim(),
        rol,
        habeas_data_aceptado: habeasDataAceptado,
        es_mayor_de_edad: esMayorDeEdad,
      })
      try {
        const sesion = await iniciarSesion({ email, password })
        return { usuario, sesion, sesionIniciada: true }
      } catch {
        // La cuenta ya existe; solo falló el ingreso automático (p. ej. sin red). Que ingrese a mano.
        return { usuario, sesion: null, sesionIniciada: false }
      }
    },

    /** El servidor revoca el token (logout); si no hay red igual se cierra en el dispositivo y se borra lo guardado. */
    async cerrarSesion() {
      // El logout con el access token también revoca el refresh: si venció, se renueva antes para poder revocar
      try {
        const token = await obtenerToken()
        if (token) await gateway.cerrarSesion(token)
      } catch { /* sin red o token ya vencido: igual se cierra en el dispositivo */ }
      store.clear()
      await Promise.resolve(localData.clearAll()).catch(() => {})
    },

    /** El backend respondió 401 y ya no se pudo renovar: la sesión no sirve. Se conserva quién era para pedir volver a ingresar. */
    invalidarSesion() {
      const s = store.load()
      if (s) store.save(vencerSesion(s))
    },

    /** UC3, paso 1: pide el enlace. La respuesta es la misma exista o no la cuenta (no revela quién está registrado). */
    async solicitarRecuperacion(email) {
      if (!emailValido(email)) rechazar([{ campo: 'email', codigo: CODIGOS_AUTH.EMAIL_INVALIDO, mensaje: 'El correo electrónico no es válido.' }])
      return gateway.solicitarRecuperacion(normalizarEmail(email))
    },

    /** UC3, paso 2: define la nueva contraseña con el token del enlace. */
    async restablecerPassword({ token, password, confirmacion }) {
      if (!token) throw new AuthError(CODIGOS_AUTH.TOKEN_INVALIDO, 'El enlace no es válido o expiró.', { status: 400 })
      const errores = validarNuevaPassword({ password, confirmacion })
      if (errores.length) rechazar(errores)
      await gateway.restablecerPassword({ token, password })
    },
  }
}
