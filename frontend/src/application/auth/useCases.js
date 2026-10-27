import { AuthError, CODIGOS_AUTH } from '../../domain/auth/errors.js'
import {
  MARGEN_EXPIRACION_MS, crearSesion, emailValido, normalizarEmail, sesionVigente, validarLogin, validarNuevaPassword, validarRegistro, vencerSesion,
} from '../../domain/auth/rules.js'
import { assertAuthGateway } from './ports.js'

/*
 * Casos de uso de autenticación (UC1 registro, UC2 inicio de sesión, UC3 recuperar contraseña,
 * UC6 consentimiento de datos). Sin Vue, sin HTTP, sin almacenamiento: todo entra por los puertos.
 */
export function createAuthUseCases({ gateway, store, localData, clock }) {
  assertAuthGateway(gateway)
  const ahora = () => clock.now()

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

  return {
    /** Estado actual: ¿hay token vigente?, ¿quién era?, ¿venció? */
    estado() {
      const s = store.load()
      const autenticado = sesionVigente(s, ahora())
      return { autenticado, usuario: s?.usuario ?? null, expirada: !!s && !autenticado }
    },

    /** Momento (ms) en que la sesión deja de servir (con el margen de seguridad), o null si no hay sesión vigente. */
    expiraEn() {
      const s = store.load()
      return sesionVigente(s, ahora()) ? s.expiraEn - MARGEN_EXPIRACION_MS : null
    },

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
      const s = store.load()
      try { if (sesionVigente(s, ahora())) await gateway.cerrarSesion(s.token) } catch { /* sin red o token ya vencido */ }
      store.clear()
      await Promise.resolve(localData.clearAll()).catch(() => {})
    },

    /** El backend respondió 401: el token ya no sirve. Se conserva quién era para pedir volver a ingresar. */
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
