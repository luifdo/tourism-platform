import { reactive } from 'vue'

/*
 * Errores que ningún componente atrapó (una excepción en un render, una promesa rechazada sin catch). Se guarda un resumen sin datos
 * personales (nombre del error y un número de referencia) para mostrar un aviso y poder reportarlo; el mensaje completo solo va a
 * la consola del navegador. Los errores de red y los de los servicios ya los trata cada pantalla: aquí solo llega lo inesperado.
 */
const estado = reactive({ hay: false, referencia: '' })

const referencia = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`.toUpperCase()

// Cosas del entorno que no son un fallo de la aplicación y que no merecen un aviso rojo: una petición cancelada (cambio de pantalla,
// tiempo máximo), la red que no responde, el Service Worker que el navegador no deja registrar (modo privado, HTTP no seguro) y el
// aviso inocuo de ResizeObserver.
const RUIDO = /ServiceWorker|Failed to fetch|NetworkError|Load failed|ResizeObserver loop|The user aborted/i
export const esRuido = (e) => e?.name === 'AbortError' || e?.name === 'TimeoutError' || RUIDO.test(String(e?.message ?? e ?? ''))

export function registrarError(e) {
  if (esRuido(e)) return
  estado.hay = true
  estado.referencia = referencia()
  console.error(`[${estado.referencia}]`, e)
}
export const descartarError = () => { estado.hay = false }
export const errorGlobal = estado
