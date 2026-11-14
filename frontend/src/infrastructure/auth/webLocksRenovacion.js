/**
 * Adaptador del puerto RenewalLock: una sola renovación del token a la vez, TAMBIÉN entre pestañas.
 * Si dos pestañas usan el mismo refresh token, iam-service lo toma como robo y cierra la sesión.
 *
 * Usa Web Locks (navigator.locks), que serializa entre pestañas y ventanas del mismo origen. Si el navegador no
 * lo tiene, serializa solo dentro de esta pestaña (mejor que nada).
 */
export function createWebLocksRenewal({ locks = globalThis.navigator?.locks, nombre = 'iam-refresh' } = {}) {
  let cola = Promise.resolve()
  return {
    run(fn) {
      if (locks?.request) return locks.request(nombre, fn)
      const p = cola.then(fn, fn) // aunque la anterior haya fallado, esta corre
      cola = p.catch(() => {})
      return p
    },
  }
}
