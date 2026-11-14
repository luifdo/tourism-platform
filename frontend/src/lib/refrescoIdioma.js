import { computed, ref, watch } from 'vue'

/*
 * Cambiar de idioma cambia al instante los textos de la interfaz (están en el paquete), pero el contenido que viene del
 * servidor (nombres y descripciones del catálogo, reseñas, zonas, alertas) se vuelve a pedir en el idioma nuevo y tarda.
 * En vez de reemplazar la pantalla por un esqueleto gris, cada pantalla conserva lo que ya muestra y avisa aquí mientras llega
 * lo nuevo: la barra fina de la parte de arriba (BarraRefresco) se enciende mientras haya algo pendiente, sean 1 o 30 peticiones.
 */
const pendientes = ref(0)
export const refrescandoIdioma = computed(() => pendientes.value > 0)

/** Ejecuta `tarea` contando una petición pendiente; si falla, el contador baja igual y el error sigue a quien llamó. */
export async function conRefresco(tarea) {
  pendientes.value += 1
  try { return await tarea() } finally { pendientes.value -= 1 }
}

/**
 * Recarga una pantalla al cambiar el idioma SIN esqueleto: hace lo mismo que su `cargar`, pero lo que ya se ve se queda hasta
 * que llega lo nuevo, y si falla se queda en el idioma anterior en vez de mostrar un error.
 *
 *  - `cargar`: el cargador de la pantalla (el mismo de siempre). Debe encender `cargando` al empezar, de forma síncrona.
 *  - `cargando`, `error`: los refs que usa para el esqueleto y para el mensaje de error.
 *  - `hayDatos()`: si no hay nada que conservar (primera carga que falló, lista vacía), se hace la carga normal con esqueleto.
 *  - `argumentos()`: argumentos para `cargar` (por ejemplo, la página en la que está el usuario, para no volver a la 1).
 *
 * Si el idioma cambia otra vez mientras una recarga está en vuelo (ES → EN → ES), no se lanza otra en paralelo: se espera a que
 * termine y se repite una vez con el idioma de ahora. Así la última respuesta que se pinta siempre es la del último idioma.
 */
export function recargarAlCambiarIdioma(locale, { cargar, cargando, error, hayDatos, argumentos = () => [] }) {
  let enCurso = false
  let repetir = false
  async function recargar() {
    if (!hayDatos()) return cargar(...argumentos())
    const promesa = cargar(...argumentos())
    cargando.value = false // el cargador lo encendió al empezar: se apaga antes de que se pinte el esqueleto
    await promesa
    error.value = '' // si falló, el contenido anterior se conserva
  }
  watch(locale, async () => {
    if (enCurso) { repetir = true; return }
    enCurso = true
    try {
      do { repetir = false; await conRefresco(recargar) } while (repetir)
    } finally { enCurso = false }
  })
}
