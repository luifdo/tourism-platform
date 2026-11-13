/*
 * PUERTOS de autenticación (lo que la aplicación necesita del exterior).
 *
 * AuthGateway  (puerto de salida; hoy lo implementa iam-service vía el Gateway)
 *   registrar({ email, password, nombre_completo, rol, habeas_data_aceptado, es_mayor_de_edad }) -> UsuarioPublico
 *   iniciarSesion({ email, password })     -> { access_token, token_type, expires_in, refresh_token, refresh_expires_in, usuario }
 *   renovar(refreshToken)                  -> lo mismo que iniciarSesion, con un access y un refresh NUEVOS
 *                                             (AuthError TOKEN_INVALIDO si venció, se revocó o ya se usó; reutilizar un
 *                                             refresh se toma como robo y el servicio cierra la sesión)
 *   cerrarSesion(token)                    -> void
 *   solicitarRecuperacion(email)           -> { enviado: true, demo?: { token } }
 *   restablecerPassword({ token, password }) -> void
 *   Los errores se lanzan como AuthError (domain/auth/errors.js).
 *
 * SessionStore (puerto de salida)  load() -> sesion | null · save(sesion) · clear()
 * RenewalLock  (puerto de salida)  run(fn) -> Promise   (una sola renovación a la vez, también entre pestañas)
 * LocalData    (puerto de salida)  clearAll() -> Promise   (borra lo guardado en el dispositivo al cerrar sesión)
 * Clock        (puerto de salida)  now() -> Date
 */
export const AUTH_GATEWAY_METHODS = Object.freeze(['registrar', 'iniciarSesion', 'renovar', 'cerrarSesion', 'solicitarRecuperacion', 'restablecerPassword'])

export function assertAuthGateway(gateway) {
  const faltan = AUTH_GATEWAY_METHODS.filter((m) => typeof gateway?.[m] !== 'function')
  if (faltan.length) throw new TypeError(`El adaptador de autenticación no implementa el puerto AuthGateway: faltan ${faltan.join(', ')}`)
  return gateway
}
