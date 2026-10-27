import { reactive, readonly } from 'vue'
import { db } from '../infrastructure/storage/idb'
import { getToken } from '../infrastructure/auth/tokenSession'

/*
 * Formularios diferidos (RNF-13, ESC-09): perfil, reseña, oferta y cupos.
 * - Cada envío lleva una Idempotency-Key para que el servidor no lo procese dos veces.
 * - Las ediciones llevan If-Match con la versión del registro; un 409 se muestra como conflicto.
 * - Solicitar y confirmar reservas NO pasan por aquí: requieren conexión.
 */
const state = reactive({ online: navigator.onLine, items: [], syncing: false })
export const queue = readonly(state)

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`)

async function refresh() {
  state.items = (await db.all('pending')).sort((a, b) => a.createdAt - b.createdAt)
}

async function send(item) {
  const headers = { 'Content-Type': 'application/json', 'Idempotency-Key': item.key }
  if (item.version != null) headers['If-Match'] = String(item.version)
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  return fetch(item.url, { method: item.method, headers, body: JSON.stringify(item.body) })
}

/** Envía ahora si hay conexión; si no (o si la red falla), lo guarda como "Pendiente de envío". */
export async function submitOrQueue({ label, method = 'POST', url, body, version }) {
  const item = { id: uid(), key: uid(), label, method, url, body, version, status: 'pending', createdAt: Date.now() }
  if (navigator.onLine) {
    try {
      const res = await send(item)
      if (res.ok) return { sent: true, res }
      if (res.status !== 0 && res.status < 500) return { sent: false, res, error: true } // error de validación: no se reintenta
    } catch { /* sin red: se encola */ }
  }
  await db.put('pending', item)
  await refresh()
  return { sent: false, queued: true, item }
}

/** Reintenta los pendientes en orden. 401 detiene el envío: hay que iniciar sesión de nuevo. */
export async function flush() {
  if (state.syncing || !navigator.onLine) return
  state.syncing = true
  try {
    for (const item of await db.all('pending')) {
      if (item.status === 'conflict' || item.status === 'failed') continue
      let res
      try { res = await send(item) } catch { break } // la red volvió a caer
      if (res.ok) await db.del('pending', item.id)
      else if (res.status === 401) { item.status = 'auth'; await db.put('pending', item); break }
      else if (res.status === 409) { item.status = 'conflict'; item.server = await res.json().catch(() => null); await db.put('pending', item) }
      else if (res.status >= 500) break
      else { item.status = 'failed'; await db.put('pending', item) }
    }
  } finally {
    state.syncing = false
    await refresh()
  }
}

export async function discard(id) { await db.del('pending', id); await refresh() }
export async function retry(id) {
  const item = await db.get('pending', id)
  if (item) { item.status = 'pending'; await db.put('pending', item) }
  await refresh()
  flush()
}
/** Al cerrar sesión se borran los datos guardados en el dispositivo. */
export async function clearLocalData() { await db.clear('pending'); await db.clear('kv'); await refresh() }

export function initOffline() {
  const set = () => { state.online = navigator.onLine; if (state.online) flush() }
  window.addEventListener('online', set)
  window.addEventListener('offline', set)
  // Sin Background Sync: también se reintenta al volver a abrir la app
  document.addEventListener('visibilitychange', () => { if (!document.hidden) flush() })
  refresh().then(() => navigator.onLine && flush())
}
