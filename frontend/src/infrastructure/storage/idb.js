// IndexedDB mínima: almacén "pending" (formularios pendientes de envío) y "kv" (catálogo en caché)
const NAME = 'samaland'

let dbp
function open() {
  dbp ??= new Promise((resolve, reject) => {
    const req = indexedDB.open(NAME, 1)
    req.onupgradeneeded = () => {
      const db = req.result
      db.createObjectStore('pending', { keyPath: 'id' })
      db.createObjectStore('kv')
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
  return dbp
}

function run(store, mode, fn) {
  return open().then((db) => new Promise((resolve, reject) => {
    const tx = db.transaction(store, mode)
    const out = fn(tx.objectStore(store))
    tx.oncomplete = () => resolve(out?.result)
    tx.onerror = () => reject(tx.error)
  }))
}

export const db = {
  all: (store) => run(store, 'readonly', (s) => s.getAll()),
  get: (store, key) => run(store, 'readonly', (s) => s.get(key)),
  put: (store, value, key) => run(store, 'readwrite', (s) => s.put(value, key)),
  del: (store, key) => run(store, 'readwrite', (s) => s.delete(key)),
  clear: (store) => run(store, 'readwrite', (s) => s.clear()),
}
