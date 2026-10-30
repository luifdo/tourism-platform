import { CODIGOS_AUTH as C } from './errors.js'

/*
 * Reglas de autenticación y registro. Son las mismas que aplica iam-service (domain/value_objects y
 * RegistrarUsuario); el cliente las comprueba antes para responder al instante, pero el servidor
 * sigue siendo la autoridad. Funciones puras: sin Vue, sin red, sin almacenamiento.
 */
export const ROLES_AUTORREGISTRO = Object.freeze(['Turista', 'Prestador'])
export const PASSWORD_MIN = 8
export const PASSWORD_MAX = 128
export const NOMBRE_MIN = 2
export const NOMBRE_MAX = 150
export const EMAIL_MAX = 254
/** El access token de iam-service dura 15 min y se descarta 30 s antes para no usar uno a punto de vencer. */
export const MARGEN_EXPIRACION_MS = 30_000

const FORMATO_EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

/** Correo normalizado como lo guarda el servidor: sin espacios a los lados y en minúsculas. */
export const normalizarEmail = (email) => String(email ?? '').trim().toLowerCase()

export function emailValido(email) {
  const e = normalizarEmail(email)
  return e.length <= EMAIL_MAX && FORMATO_EMAIL.test(e)
}

/** Estado de cada requisito de la contraseña (para mostrar una lista que se va marcando). */
export function evaluarPassword(password) {
  const p = String(password ?? '')
  const longitud = p.length >= PASSWORD_MIN && p.length <= PASSWORD_MAX
  const letra = [...p].some((c) => c.toLowerCase() !== c.toUpperCase())
  const numero = /\d/.test(p)
  return { longitud, letra, numero, valida: longitud && letra && numero }
}

const err = (campo, codigo, mensaje) => ({ campo, codigo, mensaje })

/** Valida el formulario de registro. Devuelve TODOS los problemas, uno por campo como máximo. */
export function validarRegistro({ email, password, nombre, rol, habeasDataAceptado, esMayorDeEdad }) {
  const errores = []
  if (!emailValido(email)) errores.push(err('email', C.EMAIL_INVALIDO, 'El correo electrónico no es válido.'))
  if (!evaluarPassword(password).valida)
    errores.push(err('password', C.PASSWORD_INVALIDA, `La contraseña debe tener entre ${PASSWORD_MIN} y ${PASSWORD_MAX} caracteres, con al menos una letra y un número.`))
  const largo = String(nombre ?? '').trim().length
  if (largo < NOMBRE_MIN || largo > NOMBRE_MAX)
    errores.push(err('nombre', C.NOMBRE_INVALIDO, `El nombre completo debe tener entre ${NOMBRE_MIN} y ${NOMBRE_MAX} caracteres.`))
  if (!ROLES_AUTORREGISTRO.includes(rol)) errores.push(err('rol', C.ROL_NO_PERMITIDO, 'Solo se pueden autorregistrar cuentas de Turista o Prestador.'))
  if (!habeasDataAceptado)
    errores.push(err('habeasData', C.HABEAS_DATA_REQUERIDO, 'Debe aceptar la política de tratamiento de datos personales (Ley 1581 de 2012).'))
  if (!esMayorDeEdad) errores.push(err('mayorDeEdad', C.MAYORIA_DE_EDAD_REQUERIDA, 'Debe ser mayor de edad para registrarse.'))
  return errores
}

/** El login solo exige que haya algo escrito: el servidor responde igual a un correo mal formado que a uno inexistente. */
export function validarLogin({ email, password }) {
  const errores = []
  if (!String(email ?? '').trim()) errores.push(err('email', C.EMAIL_INVALIDO, 'Escribe tu correo electrónico.'))
  if (!password) errores.push(err('password', C.PASSWORD_INVALIDA, 'Escribe tu contraseña.'))
  return errores
}

/** Nueva contraseña al restablecer: cumple la política y coincide con su confirmación. */
export function validarNuevaPassword({ password, confirmacion }) {
  const errores = []
  if (!evaluarPassword(password).valida)
    errores.push(err('password', C.PASSWORD_INVALIDA, `La contraseña debe tener entre ${PASSWORD_MIN} y ${PASSWORD_MAX} caracteres, con al menos una letra y un número.`))
  else if (password !== confirmacion) errores.push(err('confirmacion', C.PASSWORD_INVALIDA, 'Las contraseñas no coinciden.'))
  return errores
}

/**
 * Evita la redirección abierta: solo se acepta una ruta interna ('/algo'), nunca otro sitio
 * ('//otro.com', 'https://otro.com', '/\\otro.com').
 */
export function rutaSegura(destino, porDefecto = '/') {
  if (typeof destino !== 'string' || !destino.startsWith('/')) return porDefecto
  if (destino.startsWith('//') || destino.includes('\\') || /[\u0000-\u001f]/.test(destino)) return porDefecto
  return destino
}

/* ---- Sesión ---- */

/** Sesión a partir de la respuesta de POST /login: { access_token, expires_in (s), usuario } */
export function crearSesion(respuesta, ahora = new Date()) {
  return {
    token: respuesta.access_token,
    usuario: respuesta.usuario,
    expiraEn: ahora.getTime() + respuesta.expires_in * 1000,
  }
}

/** ¿El token sirve todavía? (con un margen para no usar uno a punto de vencer) */
export function sesionVigente(sesion, ahora = new Date(), margenMs = MARGEN_EXPIRACION_MS) {
  return !!sesion?.token && sesion.expiraEn - margenMs > ahora.getTime()
}

/** Marca la sesión como vencida conservando quién era (sirve para pedir volver a ingresar). */
export const vencerSesion = (sesion) => ({ ...sesion, token: null, expiraEn: 0 })
