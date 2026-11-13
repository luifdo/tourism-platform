import { db } from '../storage/idb.js'

/** Adaptador del puerto CatalogCache: la última portada del catálogo, en IndexedDB (RNF-13). */
export const idbCatalogCache = Object.freeze({
  read: () => db.get('kv', 'catalogo').then((v) => (v?.items ? { items: v.items, total: v.total ?? v.items.length, at: v.at ?? v.updatedAt ?? null } : null)),
  write: (snapshot) => db.put('kv', snapshot, 'catalogo'),
})
