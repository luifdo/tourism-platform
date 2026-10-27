import { createBookingUseCases } from './application/booking/useCases'
import { createAuthUseCases } from './application/auth/useCases'
import { createHttpBookingGateway } from './infrastructure/booking/httpBookingGateway'
import { createMockBookingGateway } from './infrastructure/booking/mockBookingGateway'
import { demoServices } from './infrastructure/booking/demoServices'
import { idbBookingCache } from './infrastructure/booking/idbBookingCache'
import { createHttpAuthGateway } from './infrastructure/auth/httpAuthGateway'
import { CUENTA_DEMO, createMockAuthGateway } from './infrastructure/auth/mockAuthGateway'
import { sessionStore } from './infrastructure/auth/sessionStore'
import { getToken, getUsuarioId, tokenSession } from './infrastructure/auth/tokenSession'
import { clearPersonalData } from './lib/offlineQueue'

/*
 * RAÍZ DE COMPOSICIÓN: el único lugar que conoce a la vez los casos de uso y los adaptadores concretos.
 * Aquí se decide qué adaptador implementa cada puerto; ninguna otra capa lo sabe.
 */
const clock = { now: () => new Date() }

// VITE_API_MOCK=false conecta con el Gateway real (iam-service y booking-service); por defecto se usan los simulados.
export const isMockBackend = import.meta.env.VITE_API_MOCK !== 'false'

/** Cuenta de ejemplo del simulador (null con el backend real) */
export const cuentaDemo = isMockBackend ? CUENTA_DEMO : null

/* ---- Autenticación (iam-service) ---- */
const authGateway = isMockBackend ? createMockAuthGateway({ clock }) : createHttpAuthGateway({ baseUrl: '/api/iam' })

export const authUseCases = createAuthUseCases({
  gateway: authGateway,
  store: sessionStore,
  localData: { clearAll: clearPersonalData }, // al cerrar sesión se borra lo personal guardado en el dispositivo
  clock,
})

/* ---- Reservas (booking-service) ---- */
const bookingGateway = isMockBackend
  ? createMockBookingGateway({ servicios: demoServices, clock, turistaId: getUsuarioId })
  : createHttpBookingGateway({ baseUrl: '/api/bookings', getToken })

// Solicitar una reserva exige sesión vigente (JWT de iam-service) también con el simulador
export const bookingUseCases = createBookingUseCases({ gateway: bookingGateway, session: tokenSession, cache: idbBookingCache, clock })
