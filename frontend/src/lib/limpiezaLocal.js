/*
 * Limpieza de lo que versiones anteriores dejaron en el dispositivo.
 *  - «catalogo»: la caché del Service Worker guardaba TODO /api/catalog/, también rutas privadas (métricas y servicios del
 *    prestador, analítica de la Entidad) y las servía a quien entrara después. Ahora se usa «catalogo-publico-v2», solo con rutas
 *    públicas y sin sesión; la vieja se borra al arrancar.
 *  - «fuentes»: ya no hay fuentes de terceros (van con la app).
 * Es idempotente y no falla donde no hay Cache Storage (HTTP no seguro, navegadores viejos).
 */
export const CACHES_OBSOLETAS = Object.freeze(['catalogo', 'fuentes'])

export async function borrarCachesObsoletas(almacen = globalThis.caches) {
  if (!almacen?.delete) return
  await Promise.all(CACHES_OBSOLETAS.map((n) => almacen.delete(n).catch(() => false)))
}
