/*
 * Limpieza de lo que versiones anteriores dejaron en el dispositivo.
 *  - «catalogo»: la caché del Service Worker guardaba TODO /api/catalog/, también rutas privadas (métricas y servicios del
 *    prestador, analítica de la Entidad) y las servía a quien entrara después. Ahora se usa «catalogo-publico-v3», solo con rutas
 *    públicas y sin sesión; la vieja se borra al arrancar.
 *  - «catalogo-publico-v2»: guardaba las respuestas por URL y el idioma va en una cabecera, así que al cambiar de idioma servía
 *    el catálogo en el idioma anterior. La v3 separa las entradas por idioma (parámetro `lang`).
 *  - «fuentes»: ya no hay fuentes de terceros (van con la app).
 * Es idempotente y no falla donde no hay Cache Storage (HTTP no seguro, navegadores viejos).
 */
export const CACHES_OBSOLETAS = Object.freeze(['catalogo', 'fuentes', 'catalogo-publico-v2'])

export async function borrarCachesObsoletas(almacen = globalThis.caches) {
  if (!almacen?.delete) return
  await Promise.all(CACHES_OBSOLETAS.map((n) => almacen.delete(n).catch(() => false)))
}
