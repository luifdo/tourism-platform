import { createBookingUseCases } from './application/booking/useCases'
import { createAuthUseCases } from './application/auth/useCases'
import { createAssistantUseCases } from './application/assistant/useCases'
import { createCatalogUseCases } from './application/catalog/useCases'
import { createProviderUseCases } from './application/provider/useCases'
import { createAccountUseCases, createAdminUseCases, createEntityUseCases, createOfferUseCases, createReviewUseCases } from './application/gestion/useCases'
import { createHttpAccountGateway, createHttpAdminGateway, createHttpEntityGateway, createHttpOfferGateway, createHttpReviewGateway } from './infrastructure/gestion/httpGestionGateways'
import { createMockGestion } from './infrastructure/gestion/mockGestion'
import { createHttpBookingGateway } from './infrastructure/booking/httpBookingGateway'
import { createMockBookingGateway } from './infrastructure/booking/mockBookingGateway'
import { demoServices } from './infrastructure/booking/demoServices'
import { idbBookingCache } from './infrastructure/booking/idbBookingCache'
import { createHttpAssistantGateway } from './infrastructure/assistant/httpAssistantGateway'
import { createMockAssistantGateway } from './infrastructure/assistant/mockAssistantGateway'
import { createHttpCatalogGateway } from './infrastructure/catalog/httpCatalogGateway'
import { createMockCatalogGateway } from './infrastructure/catalog/mockCatalogGateway'
import { idbCatalogCache } from './infrastructure/catalog/idbCatalogCache'
import { createHttpAuthGateway } from './infrastructure/auth/httpAuthGateway'
import { CUENTA_DEMO, CUENTAS_DEMO, createMockAuthGateway } from './infrastructure/auth/mockAuthGateway'
import { sessionStore } from './infrastructure/auth/sessionStore'
import { getRol, getUsuarioId, tokenSession } from './infrastructure/auth/tokenSession'
import { createAuthorizedFetch } from './infrastructure/auth/authorizedFetch'
import { createWebLocksRenewal } from './infrastructure/auth/webLocksRenovacion'
import { clearPersonalData, configurarTransporte } from './lib/offlineQueue'

/*
 * RAÍZ DE COMPOSICIÓN: el único lugar que conoce a la vez los casos de uso y los adaptadores concretos.
 * Aquí se decide qué adaptador implementa cada puerto; ninguna otra capa lo sabe.
 */
const clock = { now: () => new Date() }

// VITE_API_MOCK=false conecta con el Gateway real (iam, catalog, booking y recommendation); por defecto se usan los simulados.
export const isMockBackend = import.meta.env.VITE_API_MOCK !== 'false'

/** Cuenta de ejemplo del simulador (null con el backend real) */
export const cuentaDemo = isMockBackend ? CUENTA_DEMO : null
/** Cuentas de cada rol del simulador (Turista, Prestador, Entidad, Admin); lista vacía con el backend real */
export const cuentasDemo = isMockBackend ? CUENTAS_DEMO : []

/* ---- Autenticación (iam-service) ---- */
const authGateway = isMockBackend ? createMockAuthGateway({ clock }) : createHttpAuthGateway({ baseUrl: '/api/iam' })

export const authUseCases = createAuthUseCases({
  gateway: authGateway,
  store: sessionStore,
  localData: { clearAll: clearPersonalData }, // al cerrar sesión se borra lo personal guardado en el dispositivo
  lock: createWebLocksRenewal(), // una sola renovación del token a la vez, también entre pestañas
  clock,
})

// fetch con el access token de la sesión: lo renueva antes de vencer y, ante un 401, renueva una vez y repite
export const authorizedFetch = createAuthorizedFetch({
  tokens: {
    obtener: () => authUseCases.obtenerToken(),
    renovarTras401: async (tokenFallido) => (await authUseCases.renovarSesion({ tokenFallido }))?.token ?? null,
  },
})
configurarTransporte(authorizedFetch) // la cola sin conexión envía con ese mismo fetch

/* ---- Reservas (booking-service) ---- */
const bookingGateway = isMockBackend
  ? createMockBookingGateway({ servicios: demoServices, clock, turistaId: getUsuarioId, rolUsuario: getRol })
  : createHttpBookingGateway({ baseUrl: '/api/bookings', fetchFn: authorizedFetch })

// Solicitar una reserva exige sesión vigente (JWT de iam-service) también con el simulador
export const bookingUseCases = createBookingUseCases({ gateway: bookingGateway, session: tokenSession, cache: idbBookingCache, clock })

// Panel del prestador (UC19, UC20): el mismo adaptador de reservas implementa su puerto
export const providerUseCases = createProviderUseCases({ gateway: bookingGateway, session: tokenSession, clock })

/* ---- Asistente (recommendation-service) ---- */
const assistantGateway = isMockBackend
  ? createMockAssistantGateway({ clock, turistaId: getUsuarioId })
  : createHttpAssistantGateway({ baseUrl: '/api/recommendations', fetchFn: authorizedFetch })

// El chat exige sesión de Turista (JWT de iam-service) también con el simulador
export const assistantUseCases = createAssistantUseCases({ gateway: assistantGateway, session: tokenSession })

/* ---- Catálogo (catalog-service): rutas públicas, sin sesión ---- */
const catalogGateway = isMockBackend ? createMockCatalogGateway() : createHttpCatalogGateway({ baseUrl: '/api/catalog', authFetchFn: authorizedFetch }) // solo las rutas del prestador llevan sesión

export const catalogUseCases = createCatalogUseCases({ gateway: catalogGateway, cache: idbCatalogCache, clock })

/* ---- Gestión: perfil (UC4), documentos (UC37), oferta (UC17/18/22), reseñas, administración y entidad ---- */
// El simulador comparte un único estado (cuentas, documentos, reseñas, alertas) entre los puertos
const mock = isMockBackend
  ? createMockGestion({ directorio: authGateway.directorio, usuario: () => ({ id: getUsuarioId(), rol: getRol() }), clock })
  : null

export const accountUseCases = createAccountUseCases({ gateway: mock?.account ?? createHttpAccountGateway({ baseUrl: '/api/iam', fetchFn: authorizedFetch }) })
export const adminUseCases = createAdminUseCases({ gateway: mock?.admin ?? createHttpAdminGateway({ baseUrl: '/api/iam', fetchFn: authorizedFetch }) })
export const reviewUseCases = createReviewUseCases({ gateway: mock?.review ?? createHttpReviewGateway({ baseUrl: '/api/reviews', fetchFn: authorizedFetch }) })
export const offerUseCases = createOfferUseCases({ gateway: mock?.offer ?? createHttpOfferGateway({ baseUrl: '/api/catalog', fetchFn: authorizedFetch }) })
export const entityUseCases = createEntityUseCases({ gateway: mock?.entity ?? createHttpEntityGateway({ baseUrl: '/api/catalog', fetchFn: authorizedFetch }) })
