/**
 * fetch que lleva el access token de la sesión y lo renueva solo:
 *   1. Antes de enviar pide el token a `tokens.obtener()`, que renueva si venció.
 *   2. Si el servidor responde 401 (el token no servía: revocado, vencido, reloj desajustado), pide UNA renovación con
 *      `tokens.renovarTras401(tokenUsado)` y repite la petición UNA vez. El 401 sale del gateway (ForwardAuth), antes de
 *      llegar al servicio, así que repetir no duplica nada; además reservas y cola llevan Idempotency-Key.
 *   3. Si no se pudo renovar de forma definitiva, devuelve ese 401 tal cual: quien llama lo traduce a "ingresar de nuevo".
 * Si la renovación falla por algo pasajero (sin red, 503) el error se propaga: la sesión sigue buena y NO se da por vencida.
 *
 * tokens: { obtener(): Promise<string|null>, renovarTras401(tokenFallido): Promise<string|null> }
 */
export function createAuthorizedFetch({ fetchFn = (...a) => fetch(...a), tokens } = {}) {
  const conToken = (init, token) => ({ ...init, headers: { ...init?.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) } })

  return async (url, init = {}) => {
    const usado = await tokens.obtener()
    const res = await fetchFn(url, conToken(init, usado))
    if (res.status !== 401 || !usado) return res // sin token no hay con qué renovar
    const nuevo = await tokens.renovarTras401(usado)
    return nuevo ? fetchFn(url, conToken(init, nuevo)) : res
  }
}
