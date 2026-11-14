/**
 * Adaptador del puerto SessionStore: la sesión (token, usuario y vencimiento) en localStorage.
 * Se guarda tal cual la entrega iam-service (access token de 15 min). Sin storage no falla: simplemente no persiste.
 */
const KEY = 'session.v1'

export function createSessionStore({ storage, key = KEY } = {}) {
  // El almacenamiento se resuelve al usarlo (no al importar el módulo): así no falla donde no existe
  const st = () => storage ?? globalThis.localStorage
  return {
    load() {
      try { return JSON.parse(st()?.getItem(key)) ?? null } catch { return null }
    },
    save(sesion) {
      try { st()?.setItem(key, JSON.stringify(sesion)) } catch { /* sin almacenamiento */ }
    },
    clear() {
      try { st()?.removeItem(key) } catch { /* sin almacenamiento */ }
    },
  }
}

export const sessionStore = createSessionStore()
