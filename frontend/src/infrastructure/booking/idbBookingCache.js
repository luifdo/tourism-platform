import { db } from '../storage/idb.js'

/** Adaptador del puerto BookingCache: la última lista de reservas, en IndexedDB (RNF-13). */
export const idbBookingCache = Object.freeze({
  read: () => db.get('kv', 'misReservas').then((v) => v ?? null),
  write: (snapshot) => db.put('kv', snapshot, 'misReservas'),
})
