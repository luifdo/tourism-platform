import { sesionVigente } from '../../domain/auth/rules.js'
import { sessionStore } from './sessionStore.js'

/**
 * Adaptador del puerto Session que usan los demás módulos (reservas, cola sin conexión): el JWT
 * vigente de la sesión. Un token vencido se trata como "sin sesión".
 */
export const getToken = (store = sessionStore, ahora = new Date()) => {
  const s = store.load()
  return sesionVigente(s, ahora) ? s.token : null
}

export const getUsuarioId = (store = sessionStore) => store.load()?.usuario?.id ?? null

export const tokenSession = Object.freeze({
  isAuthenticated: () => !!getToken(),
})
