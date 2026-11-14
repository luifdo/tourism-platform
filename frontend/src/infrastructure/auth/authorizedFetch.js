/**
 * fetch que lleva el access token de la sesión y lo renueva solo:
 *   1. Antes de enviar pide el token a `tokens.obtener()`, que renueva si venció.
 *   2. Si el servidor responde 401 (el token no servía: revocado, vencido, reloj desajustado), pide UNA renovación con
 *      `tokens.renovarTras401(tokenUsado)` y repite la petición UNA vez. El 401 sale del gateway (ForwardAuth), antes de
 *      llegar al servicio, así que repetir no duplica nada; además reservas y cola llevan Idempotency-Key.
 *      (solo si el 401 es de un token inválido: ver `esTokenInvalido`; los demás 401 se entregan sin renovar)
 *   3. Si no se pudo renovar de forma definitiva, devuelve ese 401 tal cual: quien llama lo traduce a "ingresar de nuevo".
 * Si la renovación falla por algo pasajero (sin red, 503) el error se propaga: la sesión sigue buena y NO se da por vencida.
 *
 * tokens: { obtener(): Promise<string|null>, renovarTras401(tokenFallido): Promise<string|null> }
 */
// Códigos de un 401 que significan «el token no sirve» (iam-service: TOKEN_INVALIDO; catalog y booking: NO_AUTENTICADO si les llega la petición sin identidad).
const CODIGOS_DE_TOKEN = new Set(['TOKEN_INVALIDO', 'NO_AUTENTICADO'])

/**
 * ¿Este 401 es de un token que no sirve (y entonces vale renovar y repetir)? Un 401 con un código propio —p. ej. CREDENCIALES_INVALIDAS
 * al confirmar la contraseña para borrar la cuenta— NO lo es: renovar gastaría una rotación del refresh token y repetiría una petición
 * que no se puede deshacer. Sin cuerpo legible (el 401 de un proxy, un cuerpo vacío) se asume que sí, como antes.
 */
async function esTokenInvalido(res) {
  try {
    const data = await res.clone().json()
    const code = data?.code ?? data?.error
    return !code || CODIGOS_DE_TOKEN.has(code)
  } catch { return true }
}

export function createAuthorizedFetch({ fetchFn = (...a) => fetch(...a), tokens } = {}) {
  const conToken = (init, token) => ({ ...init, headers: { ...init?.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) } })

  return async (url, init = {}) => {
    const usado = await tokens.obtener()
    const res = await fetchFn(url, conToken(init, usado))
    if (res.status !== 401 || !usado) return res // sin token no hay con qué renovar
    if (!(await esTokenInvalido(res))) return res // un 401 que no es del token se entrega tal cual
    const nuevo = await tokens.renovarTras401(usado)
    return nuevo ? fetchFn(url, conToken(init, nuevo)) : res
  }
}
