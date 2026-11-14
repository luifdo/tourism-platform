import { computed, ref } from 'vue'

/*
 * Cambiar de idioma cambia al instante los textos de la interfaz (están en el paquete), pero el contenido que viene del
 * servidor (nombres y descripciones del catálogo, reseñas) se vuelve a pedir en el idioma nuevo y tarda. En vez de
 * reemplazar la pantalla por un esqueleto gris, las vistas mantienen lo que ya muestran y avisan aquí mientras llega lo
 * nuevo: la barra fina de la parte de arriba (BarraRefresco) se enciende mientras haya algo pendiente.
 */
const pendientes = ref(0)
export const refrescandoIdioma = computed(() => pendientes.value > 0)

/** Ejecuta `tarea` contando una petición pendiente; si falla, el contador baja igual y el error sigue a quien llamó. */
export async function conRefresco(tarea) {
  pendientes.value += 1
  try { return await tarea() } finally { pendientes.value -= 1 }
}
