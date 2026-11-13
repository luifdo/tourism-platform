import { sesionActiva } from '../../domain/auth/rules.js'
import { sessionStore } from './sessionStore.js'

/**
 * Adaptador del puerto Session que usan los demás módulos (reservas, chat): ¿la persona sigue dentro? Con el access
 * token vencido pero el refresh vigente, sí: el token se renueva al enviar la petición (authorizedFetch), no aquí.
 */
export const getUsuarioId = (store = sessionStore) => store.load()?.usuario?.id ?? null

export const tokenSession = Object.freeze({
  isAuthenticated: (store = sessionStore, ahora = new Date()) => sesionActiva(store.load(), ahora),
})
