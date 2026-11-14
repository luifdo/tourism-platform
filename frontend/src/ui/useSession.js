import { onMounted, reactive, readonly } from 'vue'
import { authUseCases } from '../composition'
import { flush } from '../lib/offlineQueue'

/*
 * Estado reactivo de la sesión para la interfaz. Toda la lógica está en los casos de uso de autenticación;
 * aquí solo se mantiene sincronizado lo que la UI pinta (barra, guardas de ruta, avisos de vencimiento).
 */
const estado = reactive({ autenticado: false, usuario: null, expirada: false })
let temporizador = null
let enlazado = false

const REINTENTO_MS = 30_000 // si renovar falla por algo pasajero (sin red, 503), se vuelve a intentar
const esperaHasta = (cuando) => Math.min(Math.max(cuando - Date.now(), 0), 2 ** 31 - 1) + 100

/** Renueva el token antes de que venza (o ya, si venció pero el refresh sigue sirviendo), sin esperar a la próxima petición. */
async function renovarAhora() {
  try {
    await authUseCases.renovarSesion()
    sincronizar()
  } catch {
    clearTimeout(temporizador)
    temporizador = setTimeout(renovarAhora, REINTENTO_MS) // la sesión sigue buena: no se da por vencida
  }
}

function sincronizar() {
  let e = authUseCases.estado()
  if (e.expirada) { authUseCases.invalidarSesion(); e = authUseCases.estado() } // una sesión que no se puede renovar no se deja guardada
  estado.autenticado = e.autenticado
  estado.usuario = e.usuario
  estado.expirada = e.expirada
  clearTimeout(temporizador)
  const renovar = authUseCases.renovarEn()
  if (renovar != null) { temporizador = setTimeout(renovarAhora, esperaHasta(renovar)); return }
  // Sin refresh token (sesión guardada antes del refresh): al vencer se refleja solo, sin esperar a la próxima petición
  const vence = authUseCases.expiraEn()
  if (vence) temporizador = setTimeout(sincronizar, esperaHasta(vence))
}

function enlazar() {
  if (enlazado || typeof window === 'undefined') return
  enlazado = true
  sincronizar()
  window.addEventListener('storage', (e) => { if (e.key === 'session.v1') sincronizar() }) // otra pestaña inició o cerró sesión
  document.addEventListener('visibilitychange', () => { if (!document.hidden) sincronizar() }) // volvió a la pestaña
  window.addEventListener('online', sincronizar) // volvió la red: si el token venció, se renueva antes de reenviar lo pendiente
}
enlazar()

export function useSession() {
  onMounted(sincronizar)
  return {
    sesion: readonly(estado),

    async iniciar(credenciales) {
      const s = await authUseCases.iniciarSesion(credenciales)
      sincronizar()
      flush() // con sesión nueva se reintentan los formularios que esperaban iniciar sesión
      return s
    },

    async registrar(datos) {
      const r = await authUseCases.registrar(datos)
      sincronizar()
      if (r.sesionIniciada) flush()
      return r
    },

    async salir() {
      await authUseCases.cerrarSesion()
      sincronizar()
    },

    /** El backend respondió 401: el token ya no sirve */
    expirar() {
      authUseCases.invalidarSesion()
      sincronizar()
    },

    solicitarRecuperacion: (email) => authUseCases.solicitarRecuperacion(email),
    restablecerPassword: (datos) => authUseCases.restablecerPassword(datos),
  }
}
