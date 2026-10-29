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

function sincronizar() {
  let e = authUseCases.estado()
  if (e.expirada) { authUseCases.invalidarSesion(); e = authUseCases.estado() } // un token vencido no se deja guardado
  estado.autenticado = e.autenticado
  estado.usuario = e.usuario
  estado.expirada = e.expirada
  clearTimeout(temporizador)
  const vence = authUseCases.expiraEn()
  // El token dura 15 min (sin refresh): al vencer se refleja solo, sin esperar a la próxima petición
  if (vence) temporizador = setTimeout(sincronizar, Math.min(vence - Date.now(), 2 ** 31 - 1) + 100)
}

function enlazar() {
  if (enlazado || typeof window === 'undefined') return
  enlazado = true
  sincronizar()
  window.addEventListener('storage', (e) => { if (e.key === 'session.v1') sincronizar() }) // otra pestaña inició o cerró sesión
  document.addEventListener('visibilitychange', () => { if (!document.hidden) sincronizar() }) // volvió a la pestaña
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
