import { ref } from 'vue'
import { db } from '../infrastructure/storage/idb'
import { experiences as demo } from '../data/mock'

/*
 * Catálogo con respaldo local (RF-01 + RNF-13):
 *   1. Intenta GET /api/catalog/buscar (el Service Worker lo mantiene en caché).
 *   2. Si falla, usa la última copia guardada en IndexedDB y muestra su fecha.
 *   3. Si no hay copia, muestra los datos de ejemplo.
 */
// Estado compartido: la barra de "sin conexión" muestra la misma fecha de actualización
const items = ref(demo)
const updatedAt = ref(null)
const source = ref('demo') // 'live' | 'cache' | 'demo'

export function useCatalog() {
  async function load() {
    try {
      const res = await fetch('/api/catalog/buscar', { headers: { Accept: 'application/json' } })
      if (!res.ok || !(res.headers.get('content-type') || '').includes('json')) throw new Error('catálogo no disponible')
      const data = await res.json()
      items.value = data.items ?? data
      updatedAt.value = Date.now()
      source.value = 'live'
      await db.put('kv', { items: items.value, updatedAt: updatedAt.value }, 'catalogo')
      return
    } catch { /* sin red o sin Gateway */ }
    try {
      const saved = await db.get('kv', 'catalogo')
      if (saved) { items.value = saved.items; updatedAt.value = saved.updatedAt; source.value = 'cache' }
    } catch { /* IndexedDB no disponible */ }
  }
  return { items, updatedAt, source, load }
}
