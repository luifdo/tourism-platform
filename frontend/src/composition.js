import { createBookingUseCases } from './application/booking/useCases'
import { createHttpBookingGateway } from './infrastructure/booking/httpBookingGateway'
import { createMockBookingGateway } from './infrastructure/booking/mockBookingGateway'
import { demoServices } from './infrastructure/booking/demoServices'
import { idbBookingCache } from './infrastructure/booking/idbBookingCache'
import { getToken, tokenSession } from './infrastructure/auth/tokenSession'

/*
 * RAÍZ DE COMPOSICIÓN: el único lugar que conoce a la vez los casos de uso y los adaptadores concretos.
 * Aquí se decide qué adaptador implementa cada puerto; ninguna otra capa lo sabe.
 */
const clock = { now: () => new Date() }

// VITE_API_MOCK=false conecta con el Gateway real; por defecto se usa el servicio simulado.
export const isMockBackend = import.meta.env.VITE_API_MOCK !== 'false'

const bookingGateway = isMockBackend
  ? createMockBookingGateway({ servicios: demoServices, clock })
  : createHttpBookingGateway({ baseUrl: '/api/bookings', getToken })

// En modo simulado siempre hay un turista de demostración; en real hace falta el JWT (UC2)
const session = isMockBackend ? { isAuthenticated: () => true } : tokenSession

export const bookingUseCases = createBookingUseCases({ gateway: bookingGateway, session, cache: idbBookingCache, clock })
