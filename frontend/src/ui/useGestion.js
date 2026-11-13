import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useSession } from './useSession'

/**
 * Manejo común de errores de las pantallas de gestión: traduce el código del servicio, detecta la sesión vencida
 * (401: vuelve a /ingresar) y reparte los errores de validación por campo.
 */
export function useGestion() {
  const { t, te } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const { expirar } = useSession()

  // Un 401 con un código propio (p. ej. CREDENCIALES_INVALIDAS al confirmar la contraseña) NO es sesión vencida: es un dato mal escrito.
  const esVencida = (e) => e?.code === 'NO_AUTENTICADO' || e?.code === 'TOKEN_INVALIDO'

  /** Texto para el usuario. `ns` es un espacio de nombres propio de la pantalla con códigos específicos (opcional). */
  function mensaje(e, ns) {
    const code = e?.code ?? 'generic'
    if (ns && te(`${ns}.errors.${code}`)) return t(`${ns}.errors.${code}`)
    if (te(`gestion.errors.${code}`)) return t(`gestion.errors.${code}`)
    // Un error que no sabemos explicar lleva la referencia del servidor (correlation_id): con ella se rastrea en la bitácora y los registros
    return e?.correlationId ? `${t('gestion.errors.generic')} (${t('gestion.reference')}: ${String(e.correlationId).slice(0, 36)})` : t('gestion.errors.generic')
  }

  /** campo -> texto, para pintar el error junto a cada campo. */
  function camposDe(e) {
    const salida = {}
    for (const { campo, mensaje: m } of e?.campos ?? []) {
      const clave = `gestion.fieldErrors.${m}`
      salida[campo] = te(clave) ? t(clave) : String(m)
    }
    return salida
  }

  /** Si la sesión venció, la cierra y manda a ingresar; devuelve true para que quien llama no pinte más. */
  function sesionVencida(e) {
    if (!esVencida(e)) return false
    expirar()
    router.replace({ name: 'login', query: { redirect: route.fullPath, expirada: '1' } })
    return true
  }

  return { mensaje, camposDe, sesionVencida, esVencida }
}
